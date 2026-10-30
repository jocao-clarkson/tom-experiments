package storage

import (
	"context"
	"io"
	"time"
)

// BlobStore is the object storage used for user-generated media. The
// production implementation is S3; tests use the in-memory Fake.
type BlobStore interface {
	Put(ctx context.Context, key string, r io.Reader, contentType string) error
	Delete(ctx context.Context, key string) error
	DeletePrefix(ctx context.Context, prefix string) error
	SignedURL(ctx context.Context, key string, ttl time.Duration) (string, error)
}

// Fake is an in-memory BlobStore for tests.
type Fake struct {
	Objects map[string][]byte
}

func NewFake() *Fake { return &Fake{Objects: map[string][]byte{}} }

func (f *Fake) Put(_ context.Context, key string, r io.Reader, _ string) error {
	b, err := io.ReadAll(r)
	if err != nil {
		return err
	}
	f.Objects[key] = b
	return nil
}

func (f *Fake) Delete(_ context.Context, key string) error {
	delete(f.Objects, key)
	return nil
}

func (f *Fake) DeletePrefix(_ context.Context, prefix string) error {
	for k := range f.Objects {
		if len(k) >= len(prefix) && k[:len(prefix)] == prefix {
			delete(f.Objects, k)
		}
	}
	return nil
}

func (f *Fake) SignedURL(_ context.Context, key string, ttl time.Duration) (string, error) {
	return "https://blob.test/" + key + "?ttl=" + ttl.String(), nil
}
