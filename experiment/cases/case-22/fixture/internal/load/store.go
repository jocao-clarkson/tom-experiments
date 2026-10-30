package load

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/northwind/revpipe/internal/money"
)

type Order struct {
	OrderID   string
	Amount    money.Minor
	Currency  string
	CreatedAt time.Time
}

type DayKey struct {
	Day      time.Time // truncated to UTC midnight
	Currency string
}

type Store interface {
	UpsertOrders(ctx context.Context, orders []Order) error
	RecomputeDailyRevenue(ctx context.Context, keys []DayKey) error
}

type PGStore struct{ pool *pgxpool.Pool }

func NewPGStore(ctx context.Context, dsn string) (*PGStore, error) {
	pool, err := pgxpool.New(ctx, dsn)
	if err != nil {
		return nil, err
	}
	return &PGStore{pool: pool}, nil
}

func (s *PGStore) Close() { s.pool.Close() }

func (s *PGStore) UpsertOrders(ctx context.Context, orders []Order) error {
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)
	for _, o := range orders {
		_, err := tx.Exec(ctx, `
			INSERT INTO orders (order_id, amount_minor, currency, created_at)
			VALUES ($1, $2, $3, $4)
			ON CONFLICT (order_id) DO UPDATE
			SET amount_minor = EXCLUDED.amount_minor,
			    currency = EXCLUDED.currency,
			    created_at = EXCLUDED.created_at`,
			o.OrderID, int64(o.Amount), o.Currency, o.CreatedAt)
		if err != nil {
			return err
		}
	}
	return tx.Commit(ctx)
}

// RecomputeDailyRevenue rebuilds daily_revenue rows for the given days from
// the source tables, so re-running a load never double counts.
func (s *PGStore) RecomputeDailyRevenue(ctx context.Context, keys []DayKey) error {
	for _, k := range keys {
		_, err := s.pool.Exec(ctx, `
			INSERT INTO daily_revenue (day, currency, gross_minor)
			SELECT $1::date, $2, COALESCE(SUM(amount_minor), 0)
			FROM orders
			WHERE created_at >= $1 AND created_at < $1 + interval '1 day' AND currency = $2
			ON CONFLICT (day, currency) DO UPDATE SET gross_minor = EXCLUDED.gross_minor`,
			k.Day, k.Currency)
		if err != nil {
			return err
		}
	}
	return nil
}
