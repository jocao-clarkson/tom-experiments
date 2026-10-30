package devices

import (
	"context"
	"database/sql"
	"time"

	"github.com/pebbleapp/api/internal/cache"
)

type Device struct {
	Token      string
	UserID     string
	Platform   string // "ios" | "android"
	AppVersion string
	UpdatedAt  time.Time
}

// Repo is the only place that touches the devices table.
type Repo interface {
	Upsert(ctx context.Context, d Device) error
	Delete(ctx context.Context, userID, token string) error
	ListForUser(ctx context.Context, userID string) ([]Device, error)
}

type SQLRepo struct{ db *sql.DB }

func NewSQLRepo(db *sql.DB) *SQLRepo { return &SQLRepo{db: db} }

func (r *SQLRepo) Upsert(ctx context.Context, d Device) error {
	_, err := r.db.ExecContext(ctx, `
		INSERT INTO devices (token, user_id, platform, app_version, updated_at)
		VALUES ($1, $2, $3, $4, now())
		ON CONFLICT (token) DO UPDATE
		SET user_id = EXCLUDED.user_id, platform = EXCLUDED.platform,
		    app_version = EXCLUDED.app_version, updated_at = now()`,
		d.Token, d.UserID, d.Platform, d.AppVersion)
	return err
}

func (r *SQLRepo) Delete(ctx context.Context, userID, token string) error {
	_, err := r.db.ExecContext(ctx, `DELETE FROM devices WHERE user_id = $1 AND token = $2`, userID, token)
	return err
}

func (r *SQLRepo) ListForUser(ctx context.Context, userID string) ([]Device, error) {
	rows, err := r.db.QueryContext(ctx, `
		SELECT token, user_id, platform, app_version, updated_at
		FROM devices WHERE user_id = $1`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Device
	for rows.Next() {
		var d Device
		if err := rows.Scan(&d.Token, &d.UserID, &d.Platform, &d.AppVersion, &d.UpdatedAt); err != nil {
			return nil, err
		}
		out = append(out, d)
	}
	return out, rows.Err()
}

// CachedRepo serves ListForUser from a TTL cache keyed by user ID. Writes
// through it drop that user's entry.
type CachedRepo struct {
	Repo
	cache *cache.TTL[string, []Device]
}

func NewCachedRepo(r Repo, c *cache.TTL[string, []Device]) *CachedRepo {
	return &CachedRepo{Repo: r, cache: c}
}

func (r *CachedRepo) ListForUser(ctx context.Context, userID string) ([]Device, error) {
	if devs, ok := r.cache.Get(userID); ok {
		return devs, nil
	}
	devs, err := r.Repo.ListForUser(ctx, userID)
	if err != nil {
		return nil, err
	}
	r.cache.Set(userID, devs)
	return devs, nil
}

func (r *CachedRepo) Upsert(ctx context.Context, d Device) error {
	err := r.Repo.Upsert(ctx, d)
	r.cache.Delete(d.UserID)
	return err
}

func (r *CachedRepo) Delete(ctx context.Context, userID, token string) error {
	err := r.Repo.Delete(ctx, userID, token)
	r.cache.Delete(userID)
	return err
}
