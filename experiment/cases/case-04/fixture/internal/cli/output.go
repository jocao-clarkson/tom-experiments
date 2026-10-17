package cli

import (
	"encoding/json"
	"fmt"
	"io"
	"strings"
	"text/tabwriter"
)

// Format names accepted by --format on commands that print records.
const (
	FormatTable = "table"
	FormatJSON  = "json"
)

// Table is a header plus rows of already-stringified cells.
type Table struct {
	Header []string
	Rows   [][]string
}

// WriteJSON writes v as indented JSON followed by a newline.
func WriteJSON(w io.Writer, v any) error {
	enc := json.NewEncoder(w)
	enc.SetIndent("", "  ")
	return enc.Encode(v)
}

// WriteTable writes t as aligned columns.
func WriteTable(w io.Writer, t Table) error {
	tw := tabwriter.NewWriter(w, 0, 4, 2, ' ', 0)
	fmt.Fprintln(tw, strings.Join(t.Header, "\t"))
	for _, r := range t.Rows {
		fmt.Fprintln(tw, strings.Join(r, "\t"))
	}
	return tw.Flush()
}

// CheckFormat returns a UsageError if f is not one of allowed.
func CheckFormat(f string, allowed ...string) error {
	for _, a := range allowed {
		if f == a {
			return nil
		}
	}
	return Usagef("unknown format %q (want one of: %s)", f, strings.Join(allowed, ", "))
}
