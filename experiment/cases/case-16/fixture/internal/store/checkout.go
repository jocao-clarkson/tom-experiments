package store

import (
	"context"
	"database/sql"
	"errors"

	"github.com/jackc/pgx/v5/pgconn"
)

var ErrBusy = errors.New("product rows locked")

type PriceLine struct {
	SKU        string `json:"sku"`
	PriceCents int64  `json:"price_cents"`
	Currency   string `json:"currency"`
}

// QuoteLines returns the prices checkout will charge for the given SKUs.
// Rows are read FOR SHARE so a quote never mixes old and new prices.
func (s *Store) QuoteLines(ctx context.Context, skus []string) ([]PriceLine, error) {
	var lines []PriceLine
	err := s.WithTx(ctx, func(tx *sql.Tx) error {
		if _, err := tx.ExecContext(ctx, `SET LOCAL lock_timeout = '150ms'`); err != nil {
			return err
		}
		rows, err := tx.QueryContext(ctx,
			`SELECT sku, price_cents, currency FROM products WHERE sku = ANY($1) ORDER BY sku FOR SHARE`, skus)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var l PriceLine
			if err := rows.Scan(&l.SKU, &l.PriceCents, &l.Currency); err != nil {
				return err
			}
			lines = append(lines, l)
		}
		return rows.Err()
	})
	var pgErr *pgconn.PgError
	if errors.As(err, &pgErr) && pgErr.Code == "55P03" {
		return nil, ErrBusy
	}
	return lines, err
}
