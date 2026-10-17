package api

import (
	"context"
	"net/http"
)

type ctxKey int

const userIDKey ctxKey = 1

// TokenVerifier resolves a session token to a user id.
type TokenVerifier interface {
	Verify(ctx context.Context, token string) (string, error)
}

func RequireUser(v TokenVerifier) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			const p = "Bearer "
			h := r.Header.Get("Authorization")
			if len(h) <= len(p) || h[:len(p)] != p {
				writeError(w, http.StatusUnauthorized, "unauthenticated")
				return
			}
			uid, err := v.Verify(r.Context(), h[len(p):])
			if err != nil {
				writeError(w, http.StatusUnauthorized, "unauthenticated")
				return
			}
			next.ServeHTTP(w, r.WithContext(context.WithValue(r.Context(), userIDKey, uid)))
		})
	}
}

func UserID(ctx context.Context) string {
	s, _ := ctx.Value(userIDKey).(string)
	return s
}

// LimitBody caps the request body at n bytes; reads past it fail and the
// handler should answer 413.
func LimitBody(n int64) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			r.Body = http.MaxBytesReader(w, r.Body, n)
			next.ServeHTTP(w, r)
		})
	}
}

func chain(h http.Handler, mw ...func(http.Handler) http.Handler) http.Handler {
	for i := len(mw) - 1; i >= 0; i-- {
		h = mw[i](h)
	}
	return h
}
