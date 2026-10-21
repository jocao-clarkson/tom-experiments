package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/ledgerly/iam/internal/apikey"
	"github.com/ledgerly/iam/internal/audit"
	"github.com/ledgerly/iam/internal/clock"
	"github.com/ledgerly/iam/internal/httpapi"
	"github.com/ledgerly/iam/internal/store"
)

func main() {
	ctx := context.Background()
	pool, err := pgxpool.New(ctx, mustEnv("DATABASE_URL"))
	if err != nil {
		log.Fatal(err)
	}
	defer pool.Close()

	st := store.NewPG(pool)
	clk := clock.System{}
	verifier := apikey.NewVerifier(st, clk, envDuration("KEY_CACHE_TTL", 10*time.Minute))
	keys := &httpapi.KeysAPI{
		Store: st,
		Audit: audit.NewQueue(audit.NewSQL(st), 4096),
		Clock: clk,
		NewID: newID,
	}

	addr := envOr("ADDR", ":8080")
	log.Printf("iam listening on %s", addr)
	log.Fatal(http.ListenAndServe(addr, httpapi.Routes(verifier, keys)))
}

func newID() string {
	b := make([]byte, 12)
	if _, err := rand.Read(b); err != nil {
		panic(err)
	}
	return "key_" + hex.EncodeToString(b)
}

func mustEnv(name string) string {
	v := os.Getenv(name)
	if v == "" {
		log.Fatalf("%s is required", name)
	}
	return v
}

func envOr(name, def string) string {
	if v := os.Getenv(name); v != "" {
		return v
	}
	return def
}

func envDuration(name string, def time.Duration) time.Duration {
	v := os.Getenv(name)
	if v == "" {
		return def
	}
	d, err := time.ParseDuration(v)
	if err != nil {
		log.Fatalf("%s: %v", name, err)
	}
	return d
}
