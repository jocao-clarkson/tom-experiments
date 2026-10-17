package pipeline

import (
	"context"
	"fmt"
	"io"
	"log"
	"path/filepath"
	"time"

	"github.com/northwind/revpipe/internal/config"
	"github.com/northwind/revpipe/internal/extract"
	"github.com/northwind/revpipe/internal/load"
	"github.com/northwind/revpipe/internal/money"
)

// RunOrders streams every orders_*.csv file in the input directory into the
// orders table in batches, then recomputes daily revenue for the days touched.
func RunOrders(ctx context.Context, cfg config.Config, store load.Store) error {
	files, err := filepath.Glob(filepath.Join(cfg.InputDir, "orders_*.csv"))
	if err != nil {
		return err
	}
	touched := map[load.DayKey]struct{}{}
	for _, path := range files {
		if err := loadOrdersFile(ctx, path, cfg.BatchSize, store, touched); err != nil {
			return fmt.Errorf("%s: %w", filepath.Base(path), err)
		}
	}
	keys := make([]load.DayKey, 0, len(touched))
	for k := range touched {
		keys = append(keys, k)
	}
	return store.RecomputeDailyRevenue(ctx, keys)
}

func loadOrdersFile(ctx context.Context, path string, batchSize int, store load.Store, touched map[load.DayKey]struct{}) error {
	rd, err := extract.Open(path)
	if err != nil {
		return err
	}
	defer rd.Close()

	batch := make([]load.Order, 0, batchSize)
	flush := func() error {
		if len(batch) == 0 {
			return nil
		}
		err := store.UpsertOrders(ctx, batch)
		batch = batch[:0]
		return err
	}
	for {
		rec, err := rd.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return err
		}
		amt, err := money.Parse(rec["amount"], rec["currency"])
		if err != nil {
			log.Printf("skip order %s line %d: %v", rec["order_id"], rd.Line, err)
			continue
		}
		created, err := time.Parse(time.RFC3339, rec["created_at"])
		if err != nil {
			log.Printf("skip order %s line %d: bad created_at", rec["order_id"], rd.Line)
			continue
		}
		o := load.Order{OrderID: rec["order_id"], Amount: amt, Currency: rec["currency"], CreatedAt: created.UTC()}
		batch = append(batch, o)
		touched[load.DayKey{Day: o.CreatedAt.Truncate(24 * time.Hour), Currency: o.Currency}] = struct{}{}
		if len(batch) == batchSize {
			if err := flush(); err != nil {
				return err
			}
		}
	}
	return flush()
}
