package httpapi

import (
	"context"
	"net/http"
	"slices"
	"strings"

	"github.com/ledgerly/iam/internal/apikey"
	"github.com/ledgerly/iam/internal/store"
)

// Routes builds the public API handler.
func Routes(v *apikey.Verifier, keys *KeysAPI) http.Handler {
	mux := http.NewServeMux()
	mux.Handle("POST /v1/service-accounts/{id}/keys", Authenticate(v, RequireScope("keys:admin", keys.Create)))
	mux.Handle("GET /v1/service-accounts/{id}/keys", Authenticate(v, RequireScope("keys:read", keys.List)))
	return mux
}

type ctxKey struct{}

func Authenticate(v *apikey.Verifier, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
		k, err := v.Verify(r.Context(), raw)
		if err != nil {
			writeError(w, http.StatusUnauthorized, "unauthenticated")
			return
		}
		next.ServeHTTP(w, r.WithContext(context.WithValue(r.Context(), ctxKey{}, k)))
	})
}

func RequireScope(scope string, next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		k, _ := r.Context().Value(ctxKey{}).(store.Key)
		if !slices.Contains(k.Scopes, scope) {
			writeError(w, http.StatusForbidden, "insufficient_scope")
			return
		}
		next(w, r)
	}
}

// ActorID is the id of the API key making the request.
func ActorID(ctx context.Context) string {
	k, _ := ctx.Value(ctxKey{}).(store.Key)
	return k.ID
}
