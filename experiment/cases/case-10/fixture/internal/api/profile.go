package api

import (
	"encoding/json"
	"errors"
	"net/http"
	"strings"
)

type meResponse struct {
	ID          string `json:"id"`
	DisplayName string `json:"display_name"`
	Email       string `json:"email"`
}

func (s *Server) getMe(w http.ResponseWriter, r *http.Request) {
	u, err := s.Users.Get(r.Context(), UserID(r.Context()))
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal_error")
		return
	}
	writeJSON(w, http.StatusOK, meResponse{ID: u.ID, DisplayName: u.DisplayName, Email: u.Email})
}

func (s *Server) patchMe(w http.ResponseWriter, r *http.Request) {
	var body struct {
		DisplayName *string `json:"display_name"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		var mbe *http.MaxBytesError
		if errors.As(err, &mbe) {
			writeError(w, http.StatusRequestEntityTooLarge, "body_too_large")
			return
		}
		writeError(w, http.StatusBadRequest, "invalid_json")
		return
	}
	if body.DisplayName != nil {
		name := strings.TrimSpace(*body.DisplayName)
		if name == "" || len(name) > 64 {
			writeError(w, http.StatusBadRequest, "invalid_display_name")
			return
		}
		if _, err := s.Users.DB.ExecContext(r.Context(),
			`UPDATE users SET display_name = $2 WHERE id = $1`, UserID(r.Context()), name); err != nil {
			writeError(w, http.StatusInternalServerError, "internal_error")
			return
		}
	}
	w.WriteHeader(http.StatusNoContent)
}
