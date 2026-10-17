package httpx

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"net/http"
	"strconv"
	"strings"
)

type ctxKey int

const (
	userKey ctxKey = iota
	versionKey
	requestIDKey
)

// RequireUser trusts the X-User-ID header, which the API gateway sets after
// verifying the session token and strips from client requests.
func RequireUser(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		uid := r.Header.Get("X-User-ID")
		if uid == "" {
			Error(w, http.StatusUnauthorized, "unauthenticated", "missing user", nil)
			return
		}
		next.ServeHTTP(w, r.WithContext(context.WithValue(r.Context(), userKey, uid)))
	})
}

func UserID(ctx context.Context) string {
	v, _ := ctx.Value(userKey).(string)
	return v
}

// Version is a parsed X-App-Version header ("5.1.3" -> {5,1}).
type Version struct{ Major, Minor int }

func (v Version) AtLeast(major, minor int) bool {
	return v.Major > major || (v.Major == major && v.Minor >= minor)
}

func AppVersion(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		next.ServeHTTP(w, r.WithContext(context.WithValue(r.Context(), versionKey, parseVersion(r.Header.Get("X-App-Version")))))
	})
}

func ClientVersion(ctx context.Context) Version {
	v, _ := ctx.Value(versionKey).(Version)
	return v
}

func parseVersion(s string) Version {
	parts := strings.SplitN(s, ".", 3)
	var v Version
	if len(parts) >= 1 {
		v.Major, _ = strconv.Atoi(parts[0])
	}
	if len(parts) >= 2 {
		v.Minor, _ = strconv.Atoi(parts[1])
	}
	return v
}

func RequestID(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		id := r.Header.Get("X-Request-ID")
		if id == "" {
			b := make([]byte, 8)
			_, _ = rand.Read(b)
			id = hex.EncodeToString(b)
		}
		w.Header().Set("X-Request-ID", id)
		next.ServeHTTP(w, r.WithContext(context.WithValue(r.Context(), requestIDKey, id)))
	})
}
