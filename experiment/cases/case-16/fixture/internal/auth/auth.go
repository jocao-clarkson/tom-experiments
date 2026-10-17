package auth

import (
	"context"
	"net/http"
	"slices"

	"github.com/lumenmart/catalog/internal/apierr"
)

type ctxKey struct{}

type Principal struct {
	Subject string
	Scopes  []string
}

func WithPrincipal(ctx context.Context, p Principal) context.Context {
	return context.WithValue(ctx, ctxKey{}, p)
}

func FromContext(ctx context.Context) (Principal, bool) {
	p, ok := ctx.Value(ctxKey{}).(Principal)
	return p, ok
}

// RequireScope rejects requests whose principal lacks the given scope.
// Authenticate (gateway-verified headers) must run first.
func RequireScope(scope string, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		p, ok := FromContext(r.Context())
		if !ok {
			apierr.Write(w, http.StatusUnauthorized, "unauthenticated", "missing credentials", nil)
			return
		}
		if !slices.Contains(p.Scopes, scope) {
			apierr.Write(w, http.StatusForbidden, "forbidden", "missing scope "+scope, nil)
			return
		}
		next.ServeHTTP(w, r)
	})
}
