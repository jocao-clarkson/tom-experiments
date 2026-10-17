package store

import (
	"context"
	"errors"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type PG struct {
	pool *pgxpool.Pool
	q    pgx.Tx // non-nil inside WithTx
}

func NewPG(pool *pgxpool.Pool) *PG { return &PG{pool: pool} }

func (p *PG) exec(ctx context.Context, sql string, args ...any) error {
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

func (p *PG) Exec(ctx context.Context, sql string, args ...any) error { return p.exec(ctx, sql, args...) }

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
	return p.exec(ctx, `INSERT INTO api_keys (`+keyCols+`) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)`,
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
	return p.exec(ctx, `UPDATE api_keys SET expires_at = $2 WHERE id = $1`, id, at)
}

func (p *PG) Revoke(ctx context.Context, id string, at time.Time) error {
	return p.exec(ctx, `UPDATE api_keys SET revoked_at = $2 WHERE id = $1 AND revoked_at IS NULL`, id, at)
}

func (p *PG) WithTx(ctx context.Context, fn func(tx Store, ex Execer) error) error {
	return pgx.BeginFunc(ctx, p.pool, func(t pgx.Tx) error {
		inner := &PG{pool: p.pool, q: t}
		return fn(inner, inner)
	})
}
