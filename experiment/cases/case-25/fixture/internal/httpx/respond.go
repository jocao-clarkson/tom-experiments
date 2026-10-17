package httpx

import (
	"encoding/json"
	"net/http"
)

// ErrorBody is the error envelope every endpoint returns. The mobile apps'
// shared API client decodes this shape for all error responses.
type ErrorBody struct {
	Error ErrorDetail `json:"error"`
}

type ErrorDetail struct {
	Code    string         `json:"code"`
	Message string         `json:"message"`
	Details map[string]any `json:"details,omitempty"`
}

func JSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func Error(w http.ResponseWriter, status int, code, message string, details map[string]any) {
	JSON(w, status, ErrorBody{Error: ErrorDetail{Code: code, Message: message, Details: details}})
}
