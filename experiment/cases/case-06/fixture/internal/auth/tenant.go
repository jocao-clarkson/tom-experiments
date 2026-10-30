package auth

import (
	"context"
	"net/http"
	"strings"
)

type ctxKey struct{}

// KeyResolver maps an API key to the tenant that owns it.
type KeyResolver interface {
	TenantForKey(ctx context.Context, key string) (string, bool, error)
}

// Tenant authenticates the bearer API key and stores the tenant ID in the
// request context. Handlers must scope every query by TenantID(ctx).
func Tenant(res KeyResolver, onErr func(w http.ResponseWriter, status int, code, msg string)) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			key, ok := strings.CutPrefix(r.Header.Get("Authorization"), "Bearer ")
			if !ok || key == "" {
				onErr(w, http.StatusUnauthorized, "unauthenticated", "missing API key")
				return
			}
			tenant, found, err := res.TenantForKey(r.Context(), key)
			if err != nil {
				onErr(w, http.StatusInternalServerError, "internal_error", "could not verify API key")
				return
			}
			if !found {
				onErr(w, http.StatusUnauthorized, "unauthenticated", "invalid API key")
				return
			}
			next.ServeHTTP(w, r.WithContext(context.WithValue(r.Context(), ctxKey{}, tenant)))
		})
	}
}

func TenantID(ctx context.Context) string {
	v, _ := ctx.Value(ctxKey{}).(string)
	return v
}

// WithTenant is used by tests to build an authenticated context.
func WithTenant(ctx context.Context, tenant string) context.Context {
	return context.WithValue(ctx, ctxKey{}, tenant)
}
