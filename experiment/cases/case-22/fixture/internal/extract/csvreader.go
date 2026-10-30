package extract

import (
	"encoding/csv"
	"fmt"
	"io"
	"os"
)

// Reader streams a headered CSV file one record at a time.
type Reader struct {
	f      *os.File
	r      *csv.Reader
	header []string
	Line   int
}

type Record map[string]string

func Open(path string) (*Reader, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	r := csv.NewReader(f)
	r.ReuseRecord = true
	header, err := r.Read()
	if err != nil {
		f.Close()
		return nil, fmt.Errorf("%s: reading header: %w", path, err)
	}
	return &Reader{f: f, r: r, header: append([]string(nil), header...), Line: 1}, nil
}

func (rd *Reader) Header() []string { return rd.header }

// Next returns the next record or io.EOF.
func (rd *Reader) Next() (Record, error) {
	fields, err := rd.r.Read()
	if err == io.EOF {
		return nil, io.EOF
	}
	rd.Line++
	if err != nil {
		return nil, fmt.Errorf("line %d: %w", rd.Line, err)
	}
	rec := make(Record, len(rd.header))
	for i, h := range rd.header {
		if i < len(fields) {
			rec[h] = fields[i]
		}
	}
	return rec, nil
}

func (rd *Reader) Close() error { return rd.f.Close() }
