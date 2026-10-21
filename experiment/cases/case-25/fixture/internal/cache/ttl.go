package cache

import (
	"sync"
	"time"
)

// TTL is a size-bounded, concurrency-safe cache whose entries expire a fixed
// duration after they are set.
type TTL[K comparable, V any] struct {
	mu      sync.Mutex
	ttl     time.Duration
	max     int
	entries map[K]entry[V]
	now     func() time.Time
}

type entry[V any] struct {
	val     V
	expires time.Time
}

func New[K comparable, V any](max int, ttl time.Duration) *TTL[K, V] {
	return &TTL[K, V]{ttl: ttl, max: max, entries: make(map[K]entry[V]), now: time.Now}
}

func (c *TTL[K, V]) Get(k K) (V, bool) {
	c.mu.Lock()
	defer c.mu.Unlock()
	e, ok := c.entries[k]
	if !ok || c.now().After(e.expires) {
		delete(c.entries, k)
		var zero V
		return zero, false
	}
	return e.val, true
}

func (c *TTL[K, V]) Set(k K, v V) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if _, exists := c.entries[k]; !exists && len(c.entries) >= c.max {
		c.evict()
	}
	c.entries[k] = entry[V]{val: v, expires: c.now().Add(c.ttl)}
}

func (c *TTL[K, V]) Delete(k K) {
	c.mu.Lock()
	delete(c.entries, k)
	c.mu.Unlock()
}

// evict drops expired entries, then one arbitrary entry if the cache is
// still full. Callers hold c.mu.
func (c *TTL[K, V]) evict() {
	now := c.now()
	for k, e := range c.entries {
		if now.After(e.expires) {
			delete(c.entries, k)
		}
	}
	if len(c.entries) >= c.max {
		for k := range c.entries {
			delete(c.entries, k)
			break
		}
	}
}
