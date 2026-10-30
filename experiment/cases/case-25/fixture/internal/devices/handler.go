package devices

import (
	"encoding/json"
	"net/http"

	"github.com/pebbleapp/api/internal/httpx"
)

type registerRequest struct {
	Token    string `json:"token"`
	Platform string `json:"platform"`
}

func RegisterHandler(repo Repo) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var req registerRequest
		if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 4096)).Decode(&req); err != nil {
			httpx.Error(w, http.StatusBadRequest, "invalid_body", "request body must be JSON", nil)
			return
		}
		if req.Token == "" {
			httpx.Error(w, http.StatusUnprocessableEntity, "invalid_device", "token is required",
				map[string]any{"field": "token"})
			return
		}
		if req.Platform != "ios" && req.Platform != "android" {
			httpx.Error(w, http.StatusUnprocessableEntity, "invalid_device", "platform must be ios or android",
				map[string]any{"field": "platform"})
			return
		}
		v := httpx.ClientVersion(r.Context())
		d := Device{Token: req.Token, UserID: httpx.UserID(r.Context()), Platform: req.Platform,
			AppVersion: formatVersion(v)}
		if err := repo.Upsert(r.Context(), d); err != nil {
			httpx.Error(w, http.StatusInternalServerError, "internal", "could not save device", nil)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})
}

func UnregisterHandler(repo Repo) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if err := repo.Delete(r.Context(), httpx.UserID(r.Context()), r.PathValue("token")); err != nil {
			httpx.Error(w, http.StatusInternalServerError, "internal", "could not delete device", nil)
			return
		}
		w.WriteHeader(http.StatusNoContent)
	})
}

func formatVersion(v httpx.Version) string {
	b, _ := json.Marshal([]int{v.Major, v.Minor})
	return string(b)
}
