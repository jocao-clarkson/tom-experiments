package transform

import (
	"encoding/json"
	"errors"
	"time"

	"github.com/tidewater/ingest/internal/sink"
)

// Rejected describes an input record that could not be transformed.
type Rejected struct {
	Raw    []byte
	Reason string
}

var ErrMissingEventID = errors.New("missing_event_id")

type clickEvent struct {
	EventID   string `json:"event_id"`
	UserID    string `json:"user_id"`
	Page      string `json:"page"`
	Timestamp string `json:"ts"`
}

// Clicks converts raw click events into warehouse rows. Records that cannot
// be parsed are returned in the rejected slice with a reason code.
func Clicks(raw [][]byte) ([]sink.Row, []Rejected) {
	rows := make([]sink.Row, 0, len(raw))
	var rejected []Rejected
	for _, b := range raw {
		var ev clickEvent
		if err := json.Unmarshal(b, &ev); err != nil {
			rejected = append(rejected, Rejected{Raw: b, Reason: "malformed_json"})
			continue
		}
		if ev.EventID == "" {
			rejected = append(rejected, Rejected{Raw: b, Reason: ErrMissingEventID.Error()})
			continue
		}
		ts, err := time.Parse(time.RFC3339Nano, ev.Timestamp)
		if err != nil {
			rejected = append(rejected, Rejected{Raw: b, Reason: "invalid_timestamp"})
			continue
		}
		rows = append(rows, sink.Row{
			"event_id":    ev.EventID,
			"user_id":     ev.UserID,
			"page":        ev.Page,
			"occurred_at": ts.UTC(),
		})
	}
	return rows, rejected
}
