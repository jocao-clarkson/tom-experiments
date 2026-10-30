package store

import (
	"context"
	"database/sql"
	"errors"
	"time"

	"github.com/lumenmart/catalog/internal/outbox"
)

var ErrNotFound = errors.New("product not found")

type Product struct {
	SKU        string    `json:"sku"`
	Name       string    `json:"name"`
	PriceCents int64     `json:"price_cents"`
	Currency   string    `json:"currency"`
	UpdatedAt  time.Time `json:"updated_at"`
}

// Store is the only package that issues SQL against the catalog database.
type Store struct {
	db *sql.DB
}

func New(db *sql.DB) *Store { return &Store{db: db} }

// WithTx runs fn in a transaction, committing on nil and rolling back on error.
func (s *Store) WithTx(ctx context.Context, fn func(*sql.Tx) error) error {
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	if err := fn(tx); err != nil {
		_ = tx.Rollback()
		return err
	}
	return tx.Commit()
}

func (s *Store) GetProduct(ctx context.Context, sku string) (Product, error) {
	var p Product
	err := s.db.QueryRowContext(ctx,
		`SELECT sku, name, price_cents, currency, updated_at FROM products WHERE sku = $1`, sku,
	).Scan(&p.SKU, &p.Name, &p.PriceCents, &p.Currency, &p.UpdatedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return Product{}, ErrNotFound
	}
	return p, err
}

// UpdatePrice changes one product's price and records a price_changed event atomically.
func (s *Store) UpdatePrice(ctx context.Context, sku string, cents int64, currency string) error {
	return s.WithTx(ctx, func(tx *sql.Tx) error {
		var prev int64
		err := tx.QueryRowContext(ctx,
			`SELECT price_cents FROM products WHERE sku = $1 FOR UPDATE`, sku).Scan(&prev)
		if errors.Is(err, sql.ErrNoRows) {
			return ErrNotFound
		}
		if err != nil {
			return err
		}
		if _, err := tx.ExecContext(ctx,
			`UPDATE products SET price_cents = $1, currency = $2, updated_at = now() WHERE sku = $3`,
			cents, currency, sku); err != nil {
			return err
		}
		return outbox.Enqueue(ctx, tx, outbox.Event{
			Type: "price_changed", Key: sku,
			Payload: map[string]any{
				"sku":                  sku,
				"price_cents":          cents,
				"currency":             currency,
				"previous_price_cents": prev,
			},
		})
	})
}
