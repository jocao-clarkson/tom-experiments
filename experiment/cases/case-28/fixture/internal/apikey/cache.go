package apikey

import (
	"sync"
	"time"

	"github.com/ledgerly/iam/internal/clock"
	"github.com/ledgerly/iam/internal/store"
)

type entry struct {
	key     store.Key
	expires time.Time
}

type ttlCache struct {
	mu    sync.RWMutex
	ttl   time.Duration
	clock clock.Clock
	items map[string]entry
}

func newTTLCache(ttl time.Duration, c clock.Clock) *ttlCache {
	return &ttlCache{ttl: ttl, clock: c, items: map[string]entry{}}
}

func (c *ttlCache) get(k string) (store.Key, bool) {
	c.mu.RLock()
	e, ok := c.items[k]
	c.mu.RUnlock()
	if !ok || !c.clock.Now().Before(e.expires) {
		return store.Key{}, false
	}
	return e.key, true
}

func (c *ttlCache) put(k string, v store.Key) {
	c.mu.Lock()
	c.items[k] = entry{key: v, expires: c.clock.Now().Add(c.ttl)}
	c.mu.Unlock()
}
