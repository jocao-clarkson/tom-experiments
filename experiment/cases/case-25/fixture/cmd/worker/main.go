package main

import (
	"context"
	"database/sql"
	"log"
	"net/http"
	"os"
	"strconv"
	"time"

	_ "github.com/lib/pq"

	"github.com/pebbleapp/api/internal/cache"
	"github.com/pebbleapp/api/internal/devices"
	"github.com/pebbleapp/api/internal/metrics"
	"github.com/pebbleapp/api/internal/push"
)

func main() {
	db, err := sql.Open("postgres", os.Getenv("DATABASE_URL"))
	if err != nil {
		log.Fatal(err)
	}

	cacheTTL := envDuration("CACHE_TTL", time.Minute)
	cacheSize := envInt("CACHE_SIZE", 100000)
	devRepo := devices.NewCachedRepo(devices.NewSQLRepo(db),
		cache.New[string, []devices.Device](cacheSize, cacheTTL))

	sender := &push.Sender{
		Devices: devRepo,
		Client:  &push.GatewayClient{URL: os.Getenv("PUSH_GATEWAY_URL"), HTTP: &http.Client{}},
		Timeout: envDuration("PUSH_TIMEOUT", 5*time.Second),
	}

	ctx := context.Background()
	for {
		n, err := runBatch(ctx, db, sender)
		if err != nil {
			log.Printf("push jobs: %v", err)
		}
		if n == 0 {
			time.Sleep(time.Second)
		}
	}
}

type job struct {
	ID     int64
	UserID string
	N      push.Notification
}

// runBatch claims up to 50 queued pushes, sends each one and removes it from
// the queue in the same transaction. Each push is attempted once: re-running a
// partly delivered fan-out would notify the user's other devices twice.
func runBatch(ctx context.Context, db *sql.DB, s *push.Sender) (int, error) {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return 0, err
	}
	defer tx.Rollback()

	rows, err := tx.QueryContext(ctx, `
		SELECT id, user_id, category, title, body FROM push_jobs
		ORDER BY id LIMIT 50 FOR UPDATE SKIP LOCKED`)
	if err != nil {
		return 0, err
	}
	var jobs []job
	for rows.Next() {
		var j job
		var cat string
		if err := rows.Scan(&j.ID, &j.UserID, &cat, &j.N.Title, &j.N.Body); err != nil {
			rows.Close()
			return 0, err
		}
		j.N.Category = push.Category(cat)
		jobs = append(jobs, j)
	}
	rows.Close()

	for _, j := range jobs {
		if err := s.Send(ctx, j.UserID, j.N); err != nil {
			metrics.Inc("push_job_failed_total", map[string]string{"category": string(j.N.Category)})
			log.Printf("push job %d failed: %v", j.ID, err)
		}
		if _, err := tx.ExecContext(ctx, `DELETE FROM push_jobs WHERE id = $1`, j.ID); err != nil {
			return 0, err
		}
	}
	return len(jobs), tx.Commit()
}

func envDuration(name string, def time.Duration) time.Duration {
	if d, err := time.ParseDuration(os.Getenv(name)); err == nil {
		return d
	}
	return def
}

func envInt(name string, def int) int {
	if n, err := strconv.Atoi(os.Getenv(name)); err == nil {
		return n
	}
	return def
}
