package apikey

import (
	"context"
	"testing"
	"time"

	"github.com/ledgerly/iam/internal/clock"
	"github.com/ledgerly/iam/internal/store"
)

type memStore struct {
	store.Store
	byPrefix map[string]store.Key
	lookups  int
}

func (m *memStore) GetKeyByPrefix(_ context.Context, p string) (store.Key, error) {
	m.lookups++
	k, ok := m.byPrefix[p]
	if !ok {
		return k, store.ErrNotFound
	}
	return k, nil
}

func TestVerifyCachesAndRejectsExpired(t *testing.T) {
	clk := &clock.Fixed{T: time.Date(2024, 5, 1, 0, 0, 0, 0, time.UTC)}
	gen, err := Generate()
	if err != nil {
		t.Fatal(err)
	}
	exp := clk.T.Add(time.Hour)
	ms := &memStore{byPrefix: map[string]store.Key{gen.Prefix: {ID: "k1", Prefix: gen.Prefix, Hash: gen.Hash, ExpiresAt: &exp}}}
	v := NewVerifier(ms, clk, time.Minute)

	for i := 0; i < 3; i++ {
		if _, err := v.Verify(context.Background(), gen.Plaintext); err != nil {
			t.Fatal(err)
		}
	}
	if ms.lookups != 1 {
		t.Fatalf("lookups = %d, want 1", ms.lookups)
	}
	clk.Advance(2 * time.Hour)
	if _, err := v.Verify(context.Background(), gen.Plaintext); err != ErrInvalid {
		t.Fatalf("expired key accepted: %v", err)
	}
	if _, err := v.Verify(context.Background(), "lk_deadbeef_nope"); err != ErrInvalid {
		t.Fatal("unknown key accepted")
	}
}
