// Package audit records security-relevant events in audit_events.
package audit

import (
	"context"
	"encoding/json"
	"time"

	"github.com/ledgerly/iam/internal/store"
)

type Event struct {
	Type      string            `json:"type"`
	ActorID   string            `json:"actor_id"`
	AccountID string            `json:"account_id"`
	Subject   string            `json:"subject"`
	Metadata  map[string]string `json:"metadata,omitempty"`
	At        time.Time         `json:"at"`
}

// Writer persists audit events.
type Writer interface {
	Write(ctx context.Context, ev Event) error
}

const insertSQL = `INSERT INTO audit_events (type, actor_id, account_id, subject, metadata, at)
	VALUES ($1, $2, $3, $4, $5, $6)`

// SQL writes events to audit_events through ex, which may be the pool or an
// open transaction.
type SQL struct {
	ex store.Execer
}

func NewSQL(ex store.Execer) *SQL { return &SQL{ex: ex} }

func (s *SQL) Write(ctx context.Context, ev Event) error {
	meta, err := json.Marshal(ev.Metadata)
	if err != nil {
		return err
	}
	return s.ex.Exec(ctx, insertSQL, ev.Type, ev.ActorID, ev.AccountID, ev.Subject, meta, ev.At)
}
