package store

import (
	"context"
	"errors"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

var ErrNotFound = errors.New("not found")

type Invoice struct {
	ID          string    `json:"id"`
	CustomerID  string    `json:"customer_id"`
	Status      string    `json:"status"`
	AmountCents int64     `json:"amount_cents"`
	Currency    string    `json:"currency"`
	CreatedAt   time.Time `json:"created_at"`
}

type Invoices struct {
	DB *pgxpool.Pool
}

func (s *Invoices) Get(ctx context.Context, tenantID, id string) (Invoice, error) {
	var inv Invoice
	err := s.DB.QueryRow(ctx,
		`SELECT id, customer_id, status, amount_cents, currency, created_at
		   FROM invoices WHERE tenant_id = $1 AND id = $2`, tenantID, id,
	).Scan(&inv.ID, &inv.CustomerID, &inv.Status, &inv.AmountCents, &inv.Currency, &inv.CreatedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return Invoice{}, ErrNotFound
	}
	return inv, err
}
