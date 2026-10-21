package httpapi

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/ledgerly/iam/internal/audit"
	"github.com/ledgerly/iam/internal/clock"
	"github.com/ledgerly/iam/internal/store"
)

type fakeStore struct {
	keys  map[string]store.Key
	execs []string
}

func newFakeStore() *fakeStore { return &fakeStore{keys: map[string]store.Key{}} }

func (f *fakeStore) CreateKey(_ context.Context, k store.Key) error {
	f.keys[k.ID] = k
	return nil
}

func (f *fakeStore) GetKey(_ context.Context, id string) (store.Key, error) {
	k, ok := f.keys[id]
	if !ok {
		return k, store.ErrNotFound
	}
	return k, nil
}

func (f *fakeStore) GetKeyByPrefix(_ context.Context, prefix string) (store.Key, error) {
	for _, k := range f.keys {
		if k.Prefix == prefix {
			return k, nil
		}
	}
	return store.Key{}, store.ErrNotFound
}

func (f *fakeStore) ListKeys(_ context.Context, accountID string) ([]store.Key, error) {
	var out []store.Key
	for _, k := range f.keys {
		if k.AccountID == accountID {
			out = append(out, k)
		}
	}
	return out, nil
}

func (f *fakeStore) SetExpiry(_ context.Context, id string, at time.Time) error {
	k := f.keys[id]
	k.ExpiresAt = &at
	f.keys[id] = k
	return nil
}

func (f *fakeStore) Revoke(_ context.Context, id string, at time.Time) error {
	k := f.keys[id]
	if k.RevokedAt == nil {
		k.RevokedAt = &at
		f.keys[id] = k
	}
	return nil
}

func (f *fakeStore) WithTx(_ context.Context, fn func(store.Store, store.Execer) error) error {
	return fn(f, f)
}

func (f *fakeStore) Exec(_ context.Context, sql string, _ ...any) error {
	f.execs = append(f.execs, sql)
	return nil
}

func TestCreateKey(t *testing.T) {
	fs := newFakeStore()
	clk := &clock.Fixed{T: time.Date(2024, 5, 1, 0, 0, 0, 0, time.UTC)}
	a := &KeysAPI{Store: fs, Audit: audit.NewSQL(fs), Clock: clk, NewID: func() string { return "key_1" }}

	req := httptest.NewRequest(http.MethodPost, "/v1/service-accounts/acct_1/keys", strings.NewReader(`{"scopes":["ledger:read"]}`))
	req.SetPathValue("id", "acct_1")
	rec := httptest.NewRecorder()
	a.Create(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("status = %d", rec.Code)
	}
	var resp keyResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(resp.Plaintext, "lk_"+resp.Prefix+"_") {
		t.Fatalf("plaintext %q does not match prefix %q", resp.Plaintext, resp.Prefix)
	}
	if _, ok := fs.keys["key_1"]; !ok {
		t.Fatal("key not stored")
	}
	if len(fs.execs) != 1 {
		t.Fatalf("audit writes = %d, want 1", len(fs.execs))
	}
}

func TestCreateKeyRequiresScopes(t *testing.T) {
	fs := newFakeStore()
	a := &KeysAPI{Store: fs, Audit: audit.NewSQL(fs), Clock: clock.System{}, NewID: func() string { return "key_1" }}

	req := httptest.NewRequest(http.MethodPost, "/v1/service-accounts/acct_1/keys", strings.NewReader(`{"scopes":[]}`))
	req.SetPathValue("id", "acct_1")
	rec := httptest.NewRecorder()
	a.Create(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d", rec.Code)
	}
	if len(fs.keys) != 0 {
		t.Fatal("key stored on bad request")
	}
}
