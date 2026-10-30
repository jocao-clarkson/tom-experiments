package store

import (
	"context"
	"errors"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

var ErrNotFound = errors.New("not found")

type Key struct {
	ID        string
	AccountID string
	Prefix    string
	Hash      []byte
	Scopes    []string
	CreatedAt time.Time
	ExpiresAt *time.Time
	RevokedAt *time.Time
}

// Active reports whether the key may authenticate at time now.
func (k Key) Active(now time.Time) bool {
	if k.RevokedAt != nil {
		return false
	}
	return k.ExpiresAt == nil || now.Before(*k.ExpiresAt)
}

// Execer is satisfied by both the pool and an open transaction.
type Execer interface {
	Exec(ctx context.Context, sql string, args ...any) error
}

type Store interface {
	CreateKey(ctx context.Context, k Key) error
	GetKey(ctx context.Context, id string) (Key, error)
	GetKeyByPrefix(ctx context.Context, prefix string) (Key, error)
	ListKeys(ctx context.Context, accountID string) ([]Key, error)
	SetExpiry(ctx context.Context, id string, at time.Time) error
	Revoke(ctx context.Context, id string, at time.Time) error
	// WithTx runs fn in a transaction. The Store passed to fn and the
	// Execer share that transaction.
	WithTx(ctx context.Context, fn func(tx Store, ex Execer) error) error
}

// PG is the Postgres implementation of Store.
type PG struct {
	pool *pgxpool.Pool
	q    pgx.Tx // non-nil inside WithTx
}

func NewPG(pool *pgxpool.Pool) *PG { return &PG{pool: pool} }

func (p *PG) Exec(ctx context.Context, sql string, args ...any) error {
	var err error
	if p.q != nil {
		_, err = p.q.Exec(ctx, sql, args...)
	} else {
		_, err = p.pool.Exec(ctx, sql, args...)
	}
	return err
}

func (p *PG) row(ctx context.Context, sql string, args ...any) pgx.Row {
	if p.q != nil {
		return p.q.QueryRow(ctx, sql, args...)
	}
	return p.pool.QueryRow(ctx, sql, args...)
}

const keyCols = `id, account_id, prefix, hash, scopes, created_at, expires_at, revoked_at`

func scanKey(r pgx.Row) (Key, error) {
	var k Key
	err := r.Scan(&k.ID, &k.AccountID, &k.Prefix, &k.Hash, &k.Scopes, &k.CreatedAt, &k.ExpiresAt, &k.RevokedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return k, ErrNotFound
	}
	return k, err
}

func (p *PG) CreateKey(ctx context.Context, k Key) error {
	return p.Exec(ctx, `INSERT INTO api_keys (`+keyCols+`) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)`,
		k.ID, k.AccountID, k.Prefix, k.Hash, k.Scopes, k.CreatedAt, k.ExpiresAt, k.RevokedAt)
}

func (p *PG) GetKey(ctx context.Context, id string) (Key, error) {
	return scanKey(p.row(ctx, `SELECT `+keyCols+` FROM api_keys WHERE id = $1`, id))
}

func (p *PG) GetKeyByPrefix(ctx context.Context, prefix string) (Key, error) {
	return scanKey(p.row(ctx, `SELECT `+keyCols+` FROM api_keys WHERE prefix = $1`, prefix))
}

func (p *PG) ListKeys(ctx context.Context, accountID string) ([]Key, error) {
	var rows pgx.Rows
	var err error
	q := `SELECT ` + keyCols + ` FROM api_keys WHERE account_id = $1 ORDER BY created_at`
	if p.q != nil {
		rows, err = p.q.Query(ctx, q, accountID)
	} else {
		rows, err = p.pool.Query(ctx, q, accountID)
	}
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Key
	for rows.Next() {
		k, err := scanKey(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, k)
	}
	return out, rows.Err()
}

func (p *PG) SetExpiry(ctx context.Context, id string, at time.Time) error {
	return p.Exec(ctx, `UPDATE api_keys SET expires_at = $2 WHERE id = $1`, id, at)
}

func (p *PG) Revoke(ctx context.Context, id string, at time.Time) error {
	return p.Exec(ctx, `UPDATE api_keys SET revoked_at = $2 WHERE id = $1 AND revoked_at IS NULL`, id, at)
}

// WithTx commits if fn returns nil and rolls back otherwise.
func (p *PG) WithTx(ctx context.Context, fn func(tx Store, ex Execer) error) error {
	return pgx.BeginFunc(ctx, p.pool, func(t pgx.Tx) error {
		inner := &PG{pool: p.pool, q: t}
		return fn(inner, inner)
	})
}
