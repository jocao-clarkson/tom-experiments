package httpx

import (
	"context"
	"net"
	"net/http"
	"sync"
	"time"

	"github.com/northwind/authd/internal/session"
	"github.com/northwind/authd/internal/user"
)

type ctxKey struct{}

type UserLoader interface {
	ByID(ctx context.Context, id string) (user.User, error)
}

func CurrentUser(ctx context.Context) (user.User, bool) {
	u, ok := ctx.Value(ctxKey{}).(user.User)
	return u, ok
}

// RequireAuth resolves the session cookie, loads the user and rejects disabled accounts.
func RequireAuth(store session.Store, users UserLoader, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		c, err := r.Cookie("sid")
		if err != nil {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		s, err := store.Get(r.Context(), c.Value)
		if err != nil || time.Now().After(s.ExpiresAt) {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		u, err := users.ByID(r.Context(), s.UserID)
		if err != nil || u.Disabled {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		next.ServeHTTP(w, r.WithContext(context.WithValue(r.Context(), ctxKey{}, u)))
	})
}

type window struct {
	start time.Time
	count int
}

// RateLimit allows `limit` requests per `per` for each key returned by keyFn.
func RateLimit(keyFn func(*http.Request) string, limit int, per time.Duration, next http.Handler) http.Handler {
	var mu sync.Mutex
	buckets := map[string]*window{}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		k := keyFn(r)
		mu.Lock()
		b, ok := buckets[k]
		if !ok || time.Since(b.start) > per {
			b = &window{start: time.Now()}
			buckets[k] = b
		}
		b.count++
		over := b.count > limit
		mu.Unlock()
		if over {
			http.Error(w, "too many requests", http.StatusTooManyRequests)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func ClientIP(r *http.Request) string {
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return r.RemoteAddr
	}
	return host
}
