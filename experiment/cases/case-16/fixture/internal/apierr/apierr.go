package apierr

import (
	"encoding/json"
	"net/http"
)

type Body struct {
	Error Detail `json:"error"`
}

type Detail struct {
	Code    string `json:"code"`
	Message string `json:"message"`
	Details any    `json:"details,omitempty"`
}

// Write sends the standard error envelope. All handlers use it for non-2xx responses.
func Write(w http.ResponseWriter, status int, code, message string, details any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(Body{Error: Detail{Code: code, Message: message, Details: details}})
}
