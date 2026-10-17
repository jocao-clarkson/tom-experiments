// Package audit records security-relevant events in audit_events.
package audit

import (
	"context"
	"encoding/json"
	"log"
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

const insertSQL = `INSERT INTO audit_events (type, actor_id, account_id, subject, metadata, at)
	VALUES ($1, $2, $3, $4, $5, $6)`

type Recorder struct {
	db store.Execer
	ch chan Event
}

func NewRecorder(db store.Execer, buffer int) *Recorder {
	r := &Recorder{db: db, ch: make(chan Event, buffer)}
	go r.loop()
	return r
}

// Record queues a high-volume, best-effort event (e.g. key.used). It never
// blocks the caller; if the buffer is full the event is dropped and logged.
func (r *Recorder) Record(ev Event) {
	select {
	case r.ch <- ev:
	default:
		log.Printf("audit: buffer full, dropped %s for %s", ev.Type, ev.AccountID)
	}
}

// RecordTx writes ev synchronously using the caller's transaction, so the
// event commits or rolls back together with the change it describes.
func RecordTx(ctx context.Context, ex store.Execer, ev Event) error {
	meta, err := json.Marshal(ev.Metadata)
	if err != nil {
		return err
	}
	return ex.Exec(ctx, insertSQL, ev.Type, ev.ActorID, ev.AccountID, ev.Subject, meta, ev.At)
}

func (r *Recorder) loop() {
	for ev := range r.ch {
		if err := RecordTx(context.Background(), r.db, ev); err != nil {
			log.Printf("audit: write %s failed: %v", ev.Type, err)
		}
	}
}
