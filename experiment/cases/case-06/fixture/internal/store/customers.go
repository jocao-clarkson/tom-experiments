package store

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

type Customer struct {
	ID        string    `json:"id"`
	Name      string    `json:"name"`
	Email     string    `json:"email"`
	CreatedAt time.Time `json:"created_at"`
}

// After is a keyset position for (created_at DESC, id DESC) ordering.
type After struct {
	CreatedAt time.Time
	ID        string
}

type Customers struct {
	DB *pgxpool.Pool
}

// List returns up to limit+1 customers for the tenant, newest first, so the
// caller can tell whether another page exists.
func (s *Customers) List(ctx context.Context, tenantID string, after *After, limit int) ([]Customer, error) {
	args := []any{tenantID, limit + 1}
	q := `SELECT id, name, email, created_at FROM customers WHERE tenant_id = $1`
	if after != nil {
		q += ` AND (created_at, id) < ($3, $4)`
		args = append(args, after.CreatedAt, after.ID)
	}
	q += ` ORDER BY created_at DESC, id DESC LIMIT $2`

	rows, err := s.DB.Query(ctx, q, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Customer
	for rows.Next() {
		var c Customer
		if err := rows.Scan(&c.ID, &c.Name, &c.Email, &c.CreatedAt); err != nil {
			return nil, err
		}
		out = append(out, c)
	}
	return out, rows.Err()
}
