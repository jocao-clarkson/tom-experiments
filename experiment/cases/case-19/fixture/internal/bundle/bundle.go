package bundle

import (
	"archive/tar"
	"compress/gzip"
	"io"
	"time"
)

// Writer streams files into a tar.gz without buffering whole files.
type Writer struct {
	gz *gzip.Writer
	tw *tar.Writer
}

func New(w io.Writer) *Writer {
	gz := gzip.NewWriter(w)
	return &Writer{gz: gz, tw: tar.NewWriter(gz)}
}

func (b *Writer) AddFile(name string, size int64, modTime time.Time, r io.Reader) error {
	if err := b.tw.WriteHeader(&tar.Header{Name: name, Mode: 0o600, Size: size, ModTime: modTime}); err != nil {
		return err
	}
	_, err := io.CopyN(b.tw, r, size)
	return err
}

func (b *Writer) Close() error {
	if err := b.tw.Close(); err != nil {
		return err
	}
	return b.gz.Close()
}
