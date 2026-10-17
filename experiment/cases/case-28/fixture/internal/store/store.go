package store

import (
	"context"
	"errors"
	"time"
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
