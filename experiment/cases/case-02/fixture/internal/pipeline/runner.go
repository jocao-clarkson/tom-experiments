package pipeline

import (
	"context"
	"fmt"
	"log/slog"

	"github.com/tidewater/ingest/internal/config"
	"github.com/tidewater/ingest/internal/metrics"
	"github.com/tidewater/ingest/internal/retry"
	"github.com/tidewater/ingest/internal/sink"
	"github.com/tidewater/ingest/internal/source"
	"github.com/tidewater/ingest/internal/transform"
)

// TransformFunc turns raw message values into rows plus rejected records.
type TransformFunc func(raw [][]byte) ([]sink.Row, []transform.Rejected)

// Runner moves one stream from a source into a warehouse table.
type Runner struct {
	Cfg       config.Config
	Src       source.Source
	Sink      sink.Warehouse
	Table     string
	DLQTable  string
	Transform TransformFunc
	Log       *slog.Logger
}

var (
	rowsIngested     = metrics.NewCounter("rows_ingested")
	rowsDeadLettered = metrics.NewCounter("rows_dead_lettered")
)

// Run polls until ctx is cancelled. Offsets are committed only after both the
// good rows and the dead-lettered rows of a batch have been written.
func (r *Runner) Run(ctx context.Context) error {
	for {
		if err := ctx.Err(); err != nil {
			return nil
		}
		msgs, err := r.Src.Poll(ctx, r.Cfg.BatchSize)
		if err != nil {
			return fmt.Errorf("pipeline %s: poll: %w", r.Cfg.Stream, err)
		}
		if len(msgs) == 0 {
			continue
		}
		if err := r.processBatch(ctx, msgs); err != nil {
			return err
		}
	}
}

func (r *Runner) processBatch(ctx context.Context, msgs []source.Message) error {
	raw := make([][]byte, len(msgs))
	for i, m := range msgs {
		raw[i] = m.Value
	}
	rows, rejected := r.Transform(raw)

	write := func(table string, rows []sink.Row) error {
		return retry.Do(ctx, r.Cfg.WriteAttempts, r.Cfg.RetryBase, func(ctx context.Context) error {
			return r.Sink.WriteBatch(ctx, table, rows)
		})
	}
	if err := write(r.Table, rows); err != nil {
		return fmt.Errorf("pipeline %s: write %s: %w", r.Cfg.Stream, r.Table, err)
	}
	if len(rejected) > 0 {
		if err := write(r.DLQTable, dlqRows(r.Cfg.Stream, msgs, rejected)); err != nil {
			return fmt.Errorf("pipeline %s: write %s: %w", r.Cfg.Stream, r.DLQTable, err)
		}
	}
	if err := r.Src.Commit(ctx, msgs); err != nil {
		return fmt.Errorf("pipeline %s: commit: %w", r.Cfg.Stream, err)
	}
	rowsIngested.Add(r.Cfg.Stream, len(rows))
	rowsDeadLettered.Add(r.Cfg.Stream, len(rejected))
	r.Log.Info("batch committed", "stream", r.Cfg.Stream, "rows", len(rows), "rejected", len(rejected))
	return nil
}

func dlqRows(stream string, msgs []source.Message, rejected []transform.Rejected) []sink.Row {
	out := make([]sink.Row, 0, len(rejected))
	for i, rj := range rejected {
		out = append(out, sink.Row{
			"event_id": fmt.Sprintf("%s-%d-%d-%d", stream, msgs[0].Partition, msgs[0].Offset, i),
			"stream":   stream,
			"reason":   rj.Reason,
			"payload":  string(rj.Raw),
		})
	}
	return out
}
