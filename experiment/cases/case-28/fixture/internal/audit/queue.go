package audit

import (
	"context"
	"log"
)

// Queue hands events to a background goroutine that writes them with next,
// so request handlers are not slowed down by audit inserts.
type Queue struct {
	next Writer
	ch   chan Event
}

func NewQueue(next Writer, size int) *Queue {
	q := &Queue{next: next, ch: make(chan Event, size)}
	go q.run()
	return q
}

func (q *Queue) Write(_ context.Context, ev Event) error {
	select {
	case q.ch <- ev:
	default:
		log.Printf("audit: queue full, dropped %s for %s", ev.Type, ev.AccountID)
	}
	return nil
}

func (q *Queue) run() {
	for ev := range q.ch {
		if err := q.next.Write(context.Background(), ev); err != nil {
			log.Printf("audit: write %s failed: %v", ev.Type, err)
		}
	}
}
