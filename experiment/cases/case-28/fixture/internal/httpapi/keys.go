package httpapi

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/ledgerly/iam/internal/apikey"
	"github.com/ledgerly/iam/internal/audit"
	"github.com/ledgerly/iam/internal/clock"
	"github.com/ledgerly/iam/internal/store"
)

type KeysAPI struct {
	Store store.Store
	Clock clock.Clock
	NewID func() string
}

type keyResponse struct {
	ID        string     `json:"id"`
	Prefix    string     `json:"prefix"`
	Plaintext string     `json:"plaintext,omitempty"`
	Scopes    []string   `json:"scopes"`
	CreatedAt time.Time  `json:"created_at"`
	ExpiresAt *time.Time `json:"expires_at,omitempty"`
}

// Create handles POST /v1/service-accounts/{id}/keys. Routed behind
// RequireScope("keys:admin").
func (a *KeysAPI) Create(w http.ResponseWriter, r *http.Request) {
	accountID := r.PathValue("id")
	var body struct {
		Scopes []string `json:"scopes"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || len(body.Scopes) == 0 {
		writeError(w, http.StatusBadRequest, "invalid_scopes")
		return
	}
	gen, err := apikey.Generate()
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal")
		return
	}
	now := a.Clock.Now()
	k := store.Key{ID: a.NewID(), AccountID: accountID, Prefix: gen.Prefix, Hash: gen.Hash, Scopes: body.Scopes, CreatedAt: now}
	err = a.Store.WithTx(r.Context(), func(tx store.Store, ex store.Execer) error {
		if err := tx.CreateKey(r.Context(), k); err != nil {
			return err
		}
		return audit.RecordTx(r.Context(), ex, audit.Event{
			Type: "key.created", ActorID: ActorID(r.Context()), AccountID: accountID, Subject: k.ID,
			Metadata: map[string]string{"prefix": k.Prefix}, At: now,
		})
	})
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal")
		return
	}
	writeJSON(w, http.StatusCreated, keyResponse{ID: k.ID, Prefix: k.Prefix, Plaintext: gen.Plaintext, Scopes: k.Scopes, CreatedAt: now})
}

// List handles GET /v1/service-accounts/{id}/keys.
func (a *KeysAPI) List(w http.ResponseWriter, r *http.Request) {
	keys, err := a.Store.ListKeys(r.Context(), r.PathValue("id"))
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal")
		return
	}
	out := make([]keyResponse, 0, len(keys))
	for _, k := range keys {
		if k.RevokedAt != nil {
			continue
		}
		out = append(out, keyResponse{ID: k.ID, Prefix: k.Prefix, Scopes: k.Scopes, CreatedAt: k.CreatedAt, ExpiresAt: k.ExpiresAt})
	}
	writeJSON(w, http.StatusOK, map[string]any{"keys": out})
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, status int, code string) {
	writeJSON(w, status, map[string]string{"error": code})
}
