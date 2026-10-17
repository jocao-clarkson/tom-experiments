package audit

import (
	"context"
	"log/slog"
	"time"
)

type Event struct {
	Type   string
	UserID string
	IP     string
	Fields map[string]string
}

// Emit writes an audit record to the dedicated audit stream.
func Emit(ctx context.Context, e Event) {
	attrs := []any{"type", e.Type, "user_id", e.UserID, "ip", e.IP, "at", time.Now().UTC()}
	for k, v := range e.Fields {
		attrs = append(attrs, k, v)
	}
	slog.Default().With("stream", "audit").InfoContext(ctx, "audit", attrs...)
}
