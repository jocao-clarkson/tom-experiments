//go:build integration

package store

import (
	"context"
	"database/sql"
	"errors"
	"os"
	"testing"

	_ "github.com/jackc/pgx/v5/stdlib"
)

func openTestStore(t *testing.T) (*Store, *sql.DB) {
	t.Helper()
	dsn := os.Getenv("CATALOG_TEST_DSN")
	if dsn == "" {
		t.Skip("CATALOG_TEST_DSN not set")
	}
	db, err := sql.Open("pgx", dsn)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { db.Close() })
	_, err = db.Exec(`TRUNCATE products, outbox;
		INSERT INTO products (sku, name, price_cents, currency) VALUES
		('MUG-01', 'Mug', 1200, 'USD'), ('LAMP-02', 'Lamp', 4500, 'USD')`)
	if err != nil {
		t.Fatal(err)
	}
	return New(db), db
}

func TestUpdatePriceWritesOutbox(t *testing.T) {
	s, db := openTestStore(t)
	if err := s.UpdatePrice(context.Background(), "MUG-01", 999, "USD"); err != nil {
		t.Fatal(err)
	}
	var prev int64
	err := db.QueryRow(`SELECT (payload->>'previous_price_cents')::bigint FROM outbox WHERE event_key = 'MUG-01'`).Scan(&prev)
	if err != nil || prev != 1200 {
		t.Fatalf("outbox previous_price_cents = %d, err %v", prev, err)
	}
}

func TestUpdatePriceUnknownSKU(t *testing.T) {
	s, db := openTestStore(t)
	err := s.UpdatePrice(context.Background(), "NOPE-99", 999, "USD")
	if !errors.Is(err, ErrNotFound) {
		t.Fatalf("err = %v, want ErrNotFound", err)
	}
	var n int
	_ = db.QueryRow(`SELECT count(*) FROM outbox`).Scan(&n)
	if n != 0 {
		t.Fatalf("outbox rows = %d, want 0", n)
	}
}
