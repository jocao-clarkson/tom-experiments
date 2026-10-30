package httpapi

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"time"
)

const (
	defaultLimit = 50
	maxLimit     = 200
)

var errBadCursor = errors.New("invalid cursor")

// Cursor is the keyset position after the last row of a page, for lists
// ordered by (created_at DESC, id DESC).
type Cursor struct {
	CreatedAt time.Time
	ID        string
}

// wireCursor is the compact form handed to clients.
type wireCursor struct {
	C int64  `json:"c"`
	I string `json:"i"`
}

func encodeCursor(c Cursor) string {
	b, _ := json.Marshal(wireCursor{C: c.CreatedAt.UnixMilli(), I: c.ID})
	return base64.RawURLEncoding.EncodeToString(b)
}

func decodeCursor(s string) (*Cursor, error) {
	if s == "" {
		return nil, nil
	}
	b, err := base64.RawURLEncoding.DecodeString(s)
	if err != nil {
		return nil, errBadCursor
	}
	var wc wireCursor
	if err := json.Unmarshal(b, &wc); err != nil || wc.I == "" {
		return nil, errBadCursor
	}
	return &Cursor{CreatedAt: time.UnixMilli(wc.C).UTC(), ID: wc.I}, nil
}

// parseLimit reads ?limit=, defaulting to 50 and rejecting values outside 1..200.
func parseLimit(r *http.Request) (int, error) {
	v := r.URL.Query().Get("limit")
	if v == "" {
		return defaultLimit, nil
	}
	n, err := strconv.Atoi(v)
	if err != nil || n < 1 || n > maxLimit {
		return 0, errors.New("limit must be an integer between 1 and 200")
	}
	return n, nil
}
