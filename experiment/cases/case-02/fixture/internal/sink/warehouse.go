package sink

import (
	"context"
	"database/sql"
	"fmt"
	"sort"
	"strings"
)

// Row is a single output record keyed by column name.
type Row map[string]any

// Warehouse writes batches of rows to the analytics warehouse.
type Warehouse interface {
	WriteBatch(ctx context.Context, table string, rows []Row) error
}

// ConflictPolicy decides what happens to a row whose event_id is already
// stored.
type ConflictPolicy int

const (
	// SkipExisting keeps the stored row, which makes redelivered batches safe
	// to write again.
	SkipExisting ConflictPolicy = iota
	// Overwrite replaces the stored row with the incoming one. Use it for
	// streams whose events are corrected upstream.
	Overwrite
)

type PostgresWarehouse struct {
	DB         *sql.DB
	OnConflict ConflictPolicy
}

// WriteBatch writes rows in a single transaction, keyed by event_id.
func (w *PostgresWarehouse) WriteBatch(ctx context.Context, table string, rows []Row) error {
	if len(rows) == 0 {
		return nil
	}
	cols := columns(rows[0])
	tx, err := w.DB.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("sink: begin: %w", err)
	}
	defer tx.Rollback()

	stmt := buildInsert(table, cols, w.OnConflict)
	for _, r := range rows {
		args := make([]any, len(cols))
		for i, c := range cols {
			args[i] = r[c]
		}
		if _, err := tx.ExecContext(ctx, stmt, args...); err != nil {
			return fmt.Errorf("sink: insert into %s: %w", table, err)
		}
	}
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("sink: commit: %w", err)
	}
	return nil
}

func buildInsert(table string, cols []string, policy ConflictPolicy) string {
	ph := make([]string, len(cols))
	for i := range cols {
		ph[i] = fmt.Sprintf("$%d", i+1)
	}
	insert := fmt.Sprintf("INSERT INTO %s (%s) VALUES (%s)",
		table, strings.Join(cols, ", "), strings.Join(ph, ", "))

	switch policy {
	case Overwrite:
		set := make([]string, 0, len(cols))
		for _, c := range cols {
			if c == "event_id" {
				continue
			}
			set = append(set, fmt.Sprintf("%s = EXCLUDED.%s", c, c))
		}
		return insert + " ON CONFLICT (event_id) DO UPDATE SET " + strings.Join(set, ", ")
	default:
		return insert + " ON CONFLICT (event_id) DO NOTHING"
	}
}

func columns(r Row) []string {
	cols := make([]string, 0, len(r))
	for c := range r {
		cols = append(cols, c)
	}
	sort.Strings(cols)
	return cols
}
