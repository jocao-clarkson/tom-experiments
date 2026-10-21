package api

import (
	"database/sql"
	"encoding/json"
	"net/http"

	"github.com/fernway/app-backend/internal/config"
	"github.com/fernway/app-backend/internal/media"
	"github.com/fernway/app-backend/internal/storage"
	"github.com/fernway/app-backend/internal/users"
)

// DefaultBodyLimit applies to every JSON endpoint.
const DefaultBodyLimit = 64 << 10

type Server struct {
	Users  *users.Repo
	Blobs  storage.BlobStore
	Tokens TokenVerifier
}

func NewServer(cfg config.Config, db *sql.DB, blobs storage.BlobStore, tokens TokenVerifier) *Server {
	media.MaxPixels = cfg.MaxImagePixels
	return &Server{
		Users:  &users.Repo{DB: db},
		Blobs:  blobs,
		Tokens: tokens,
	}
}

func (s *Server) Routes() http.Handler {
	mux := http.NewServeMux()
	authed := func(h http.HandlerFunc, limit int64) http.Handler {
		return chain(h, LimitBody(limit), RequireUser(s.Tokens))
	}

	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]bool{"ok": true})
	})
	mux.Handle("GET /v1/me", authed(s.getMe, DefaultBodyLimit))
	mux.Handle("PATCH /v1/me", authed(s.patchMe, DefaultBodyLimit))
	return mux
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, status int, code string) {
	writeJSON(w, status, map[string]any{"error": map[string]string{"code": code}})
}
