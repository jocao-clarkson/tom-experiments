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

type PostgresWarehouse struct {
	DB *sql.DB
}

// WriteBatch inserts rows in a single transaction. Rows are keyed by
// event_id; a row whose event_id already exists is skipped, which makes
// redelivered batches safe to write again.
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

	stmt := buildInsert(table, cols)
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

func buildInsert(table string, cols []string) string {
	ph := make([]string, len(cols))
	for i := range cols {
		ph[i] = fmt.Sprintf("$%d", i+1)
	}
	return fmt.Sprintf(
		"INSERT INTO %s (%s) VALUES (%s) ON CONFLICT (event_id) DO NOTHING",
		table, strings.Join(cols, ", "), strings.Join(ph, ", "),
	)
}

func columns(r Row) []string {
	cols := make([]string, 0, len(r))
	for c := range r {
		cols = append(cols, c)
	}
	sort.Strings(cols)
	return cols
}
