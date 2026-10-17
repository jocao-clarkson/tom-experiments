package outbox

import (
	"context"
	"database/sql"
	"encoding/json"
)

type Event struct {
	Type    string
	Key     string
	Payload any
}

// Enqueue records an event in the outbox inside the caller's transaction.
// The relay process publishes committed rows to Kafka.
func Enqueue(ctx context.Context, tx *sql.Tx, e Event) error {
	b, err := json.Marshal(e.Payload)
	if err != nil {
		return err
	}
	_, err = tx.ExecContext(ctx, `INSERT INTO outbox (event_type, event_key, payload) VALUES ($1, $2, $3)`, e.Type, e.Key, b)
	return err
}
