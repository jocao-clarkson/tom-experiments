package api

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"

	_ "github.com/jackc/pgx/v5/stdlib"

	"github.com/fernway/app-backend/internal/config"
	"github.com/fernway/app-backend/internal/storage"
)

type stubTokens map[string]string

func (s stubTokens) Verify(_ context.Context, tok string) (string, error) {
	if id, ok := s[tok]; ok {
		return id, nil
	}
	return "", errors.New("unknown token")
}

func testDB(t *testing.T) *sql.DB {
	t.Helper()
	url := os.Getenv("TEST_DATABASE_URL")
	if url == "" {
		t.Skip("TEST_DATABASE_URL not set")
	}
	db, err := sql.Open("pgx", url)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { db.Close() })
	return db
}

func seedUser(t *testing.T, db *sql.DB, id, name, email string) {
	t.Helper()
	_, err := db.Exec(`INSERT INTO users (id, display_name, email, avatar_version) VALUES ($1, $2, $3, 0)
		ON CONFLICT (id) DO UPDATE SET display_name = $2, email = $3, avatar_version = 0`, id, name, email)
	if err != nil {
		t.Fatal(err)
	}
}

func newTestServer(t *testing.T, db *sql.DB) http.Handler {
	t.Helper()
	return NewServer(config.Load(), db, storage.NewFake(), stubTokens{"tok-u1": "u1"}).Routes()
}

func do(h http.Handler, method, path, body string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer tok-u1")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

func TestGetMe(t *testing.T) {
	db := testDB(t)
	seedUser(t, db, "u1", "Ada", "ada@example.com")

	rec := do(newTestServer(t, db), http.MethodGet, "/v1/me", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d", rec.Code)
	}
	var got meResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatal(err)
	}
	if got.ID != "u1" || got.DisplayName != "Ada" {
		t.Fatalf("got %+v", got)
	}
}

func TestPatchMeRejectsLongName(t *testing.T) {
	db := testDB(t)
	seedUser(t, db, "u1", "Ada", "ada@example.com")

	rec := do(newTestServer(t, db), http.MethodPatch, "/v1/me", `{"display_name":"`+strings.Repeat("x", 65)+`"}`)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d", rec.Code)
	}
}

func TestRequiresToken(t *testing.T) {
	h := NewServer(config.Load(), nil, storage.NewFake(), stubTokens{}).Routes()
	rec := do(h, http.MethodGet, "/v1/me", "")
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d", rec.Code)
	}
}
