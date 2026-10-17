package cache

import (
	"sync"
	"time"
)

type entry[V any] struct {
	value   V
	expires time.Time
}

// TTL is a small in-process cache. Each replica has its own copy.
type TTL[V any] struct {
	mu  sync.RWMutex
	ttl time.Duration
	m   map[string]entry[V]
}

func NewTTL[V any](ttl time.Duration) *TTL[V] {
	return &TTL[V]{ttl: ttl, m: map[string]entry[V]{}}
}

func (c *TTL[V]) Get(key string) (V, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	e, ok := c.m[key]
	if !ok || time.Now().After(e.expires) {
		var zero V
		return zero, false
	}
	return e.value, true
}

func (c *TTL[V]) Set(key string, v V) {
	c.mu.Lock()
	c.m[key] = entry[V]{value: v, expires: time.Now().Add(c.ttl)}
	c.mu.Unlock()
}

func (c *TTL[V]) Delete(keys ...string) {
	c.mu.Lock()
	for _, k := range keys {
		delete(c.m, k)
	}
	c.mu.Unlock()
}
