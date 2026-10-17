package notify

import (
	"context"
	"log/slog"
	"sync"
)

type Message struct {
	To       string
	Template string
	Data     map[string]string
}

type Sender interface {
	Send(ctx context.Context, m Message) error
}

// Queue delivers messages on a background worker so request handlers never wait on mail.
type Queue struct {
	ch     chan Message
	sender Sender
}

func NewQueue(sender Sender, size int) *Queue {
	q := &Queue{ch: make(chan Message, size), sender: sender}
	go q.loop()
	return q
}

func (q *Queue) Enqueue(m Message) {
	select {
	case q.ch <- m:
	default:
		slog.Warn("notify queue full, dropping message", "template", m.Template)
	}
}

func (q *Queue) loop() {
	for m := range q.ch {
		if err := q.sender.Send(context.Background(), m); err != nil {
			slog.Error("notify send failed", "template", m.Template, "err", err)
		}
	}
}

// Recorder is an in-memory Sender for tests.
type Recorder struct {
	mu   sync.Mutex
	Sent []Message
}

func (r *Recorder) Send(_ context.Context, m Message) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.Sent = append(r.Sent, m)
	return nil
}
