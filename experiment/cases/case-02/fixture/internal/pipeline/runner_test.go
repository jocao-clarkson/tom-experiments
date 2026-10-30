package pipeline

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"testing"
	"time"

	"github.com/tidewater/ingest/internal/config"
	"github.com/tidewater/ingest/internal/sink"
	"github.com/tidewater/ingest/internal/source"
	"github.com/tidewater/ingest/internal/transform"
)

type fakeSource struct {
	batches   [][]source.Message
	committed []source.Message
}

func (f *fakeSource) Poll(ctx context.Context, max int) ([]source.Message, error) {
	if len(f.batches) == 0 {
		return nil, context.Canceled
	}
	b := f.batches[0]
	f.batches = f.batches[1:]
	return b, nil
}

func (f *fakeSource) Commit(ctx context.Context, msgs []source.Message) error {
	f.committed = append(f.committed, msgs...)
	return nil
}

func (f *fakeSource) Close() error { return nil }

type fakeSink struct {
	failures int
	writes   map[string][]sink.Row
}

func (f *fakeSink) WriteBatch(ctx context.Context, table string, rows []sink.Row) error {
	if f.failures > 0 {
		f.failures--
		return errors.New("connection reset")
	}
	if f.writes == nil {
		f.writes = map[string][]sink.Row{}
	}
	f.writes[table] = append(f.writes[table], rows...)
	return nil
}

func newRunner(src *fakeSource, snk *fakeSink) *Runner {
	return &Runner{
		Cfg:       config.Config{Stream: "CLICKS", BatchSize: 10, WriteAttempts: 3, RetryBase: time.Millisecond},
		Src:       src,
		Sink:      snk,
		Table:     "clicks",
		DLQTable:  "clicks_dlq",
		Transform: transform.Clicks,
		Log:       slog.New(slog.NewTextHandler(io.Discard, nil)),
	}
}

func msg(off int64, v string) source.Message {
	return source.Message{Partition: 0, Offset: off, Value: []byte(v)}
}

func TestBatchWrittenThenCommitted(t *testing.T) {
	src := &fakeSource{batches: [][]source.Message{{
		msg(1, `{"event_id":"a","user_id":"u","page":"/","ts":"2024-05-01T10:00:00Z"}`),
		msg(2, `{"user_id":"u","page":"/","ts":"2024-05-01T10:00:00Z"}`),
	}}}
	snk := &fakeSink{}
	_ = newRunner(src, snk).processBatch(context.Background(), src.batches[0])

	if got := len(snk.writes["clicks"]); got != 1 {
		t.Fatalf("clicks rows = %d, want 1", got)
	}
	if got := snk.writes["clicks_dlq"][0]["reason"]; got != "missing_event_id" {
		t.Fatalf("dlq reason = %v", got)
	}
	if len(src.committed) != 2 {
		t.Fatalf("committed = %d, want 2", len(src.committed))
	}
}

func TestWriteFailureDoesNotCommit(t *testing.T) {
	batch := []source.Message{msg(1, `{"event_id":"a","ts":"2024-05-01T10:00:00Z"}`)}
	src := &fakeSource{}
	snk := &fakeSink{failures: 5}
	err := newRunner(src, snk).processBatch(context.Background(), batch)
	if err == nil {
		t.Fatal("expected error after exhausting attempts")
	}
	if len(src.committed) != 0 {
		t.Fatalf("committed %d messages after failed write", len(src.committed))
	}
}
