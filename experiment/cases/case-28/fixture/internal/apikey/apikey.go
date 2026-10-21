// Package apikey generates and verifies service-account API keys.
//
// Format: lk_<prefix>_<secret>, where prefix is 8 hex chars used for lookup
// and only sha256(secret) is stored.
package apikey

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"errors"
	"strings"
	"sync"
	"time"

	"github.com/ledgerly/iam/internal/clock"
	"github.com/ledgerly/iam/internal/store"
)

var ErrInvalid = errors.New("invalid api key")

type Generated struct {
	Plaintext string
	Prefix    string
	Hash      []byte
}

func Generate() (Generated, error) {
	p := make([]byte, 4)
	s := make([]byte, 24)
	if _, err := rand.Read(p); err != nil {
		return Generated{}, err
	}
	if _, err := rand.Read(s); err != nil {
		return Generated{}, err
	}
	prefix, secret := hex.EncodeToString(p), hex.EncodeToString(s)
	sum := sha256.Sum256([]byte(secret))
	return Generated{Plaintext: "lk_" + prefix + "_" + secret, Prefix: prefix, Hash: sum[:]}, nil
}

type Verifier struct {
	store store.Store
	clock clock.Clock
	cache *ttlCache
}

// NewVerifier builds the request-path verifier. Successful verifications are
// cached for cacheTTL so that steady traffic does not hit the database.
func NewVerifier(s store.Store, c clock.Clock, cacheTTL time.Duration) *Verifier {
	return &Verifier{store: s, clock: c, cache: newTTLCache(cacheTTL, c)}
}

func (v *Verifier) Verify(ctx context.Context, plaintext string) (store.Key, error) {
	parts := strings.SplitN(plaintext, "_", 3)
	if len(parts) != 3 || parts[0] != "lk" {
		return store.Key{}, ErrInvalid
	}
	sum := sha256.Sum256([]byte(parts[2]))
	cacheKey := hex.EncodeToString(sum[:])
	if k, ok := v.cache.get(cacheKey); ok {
		return k, nil
	}
	k, err := v.store.GetKeyByPrefix(ctx, parts[1])
	if err != nil {
		return store.Key{}, ErrInvalid
	}
	if subtle.ConstantTimeCompare(k.Hash, sum[:]) != 1 || !k.Active(v.clock.Now()) {
		return store.Key{}, ErrInvalid
	}
	v.cache.put(cacheKey, k)
	return k, nil
}

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
