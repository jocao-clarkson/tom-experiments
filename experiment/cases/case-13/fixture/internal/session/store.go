package session

import (
	"context"
	"encoding/json"
	"errors"
	"time"

	"github.com/redis/go-redis/v9"
)

var ErrNotFound = errors.New("session not found")

type Session struct {
	ID        string    `json:"id"`
	UserID    string    `json:"user_id"`
	IssuedAt  time.Time `json:"issued_at"`
	ExpiresAt time.Time `json:"expires_at"`
	UserAgent string    `json:"user_agent"`
}

// Store is implemented by RedisStore in production and by fakes in tests.
type Store interface {
	Create(ctx context.Context, s Session) error
	Get(ctx context.Context, id string) (Session, error)
	Delete(ctx context.Context, id string) error
}

type RedisStore struct {
	rdb *redis.Client
}

func NewRedisStore(rdb *redis.Client) *RedisStore { return &RedisStore{rdb: rdb} }

func key(id string) string { return "sess:" + id }

func (r *RedisStore) Create(ctx context.Context, s Session) error {
	b, err := json.Marshal(s)
	if err != nil {
		return err
	}
	return r.rdb.Set(ctx, key(s.ID), b, time.Until(s.ExpiresAt)).Err()
}

func (r *RedisStore) Get(ctx context.Context, id string) (Session, error) {
	b, err := r.rdb.Get(ctx, key(id)).Bytes()
	if errors.Is(err, redis.Nil) {
		return Session{}, ErrNotFound
	}
	if err != nil {
		return Session{}, err
	}
	var s Session
	return s, json.Unmarshal(b, &s)
}

func (r *RedisStore) Delete(ctx context.Context, id string) error {
	return r.rdb.Del(ctx, key(id)).Err()
}
