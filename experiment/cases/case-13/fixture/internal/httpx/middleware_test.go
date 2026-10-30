package httpx

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/northwind/authd/internal/session"
	"github.com/northwind/authd/internal/user"
)

type fakeStore struct{ m map[string]session.Session }

func (f *fakeStore) Create(_ context.Context, s session.Session) error { f.m[s.ID] = s; return nil }
func (f *fakeStore) Get(_ context.Context, id string) (session.Session, error) {
	s, ok := f.m[id]
	if !ok {
		return session.Session{}, session.ErrNotFound
	}
	return s, nil
}
func (f *fakeStore) Delete(_ context.Context, id string) error { delete(f.m, id); return nil }

type fakeUsers map[string]user.User

func (f fakeUsers) ByID(_ context.Context, id string) (user.User, error) {
	u, ok := f[id]
	if !ok {
		return user.User{}, user.ErrNotFound
	}
	return u, nil
}

func TestRequireAuthRejectsDisabledUser(t *testing.T) {
	store := &fakeStore{m: map[string]session.Session{"s1": {ID: "s1", UserID: "u1", ExpiresAt: time.Now().Add(time.Hour)}}}
	users := fakeUsers{"u1": {ID: "u1", Disabled: true}}
	h := RequireAuth(store, users, http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(200) }))

	req := httptest.NewRequest("GET", "/me", nil)
	req.AddCookie(&http.Cookie{Name: "sid", Value: "s1"})
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("want 401, got %d", rec.Code)
	}
}

func TestRateLimitBlocksAfterLimit(t *testing.T) {
	h := RateLimit(func(*http.Request) string { return "k" }, 2, time.Minute, http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {}))
	codes := []int{}
	for i := 0; i < 3; i++ {
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, httptest.NewRequest("POST", "/login", nil))
		codes = append(codes, rec.Code)
	}
	if codes[2] != http.StatusTooManyRequests {
		t.Fatalf("want 429 on third request, got %v", codes)
	}
}
