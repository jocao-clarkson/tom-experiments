package httpapi

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/quillpay/billing-api/internal/auth"
	"github.com/quillpay/billing-api/internal/store"
)

type fakeCustomers struct {
	all       []store.Customer
	gotTenant string
	gotAfter  *store.After
}

func (f *fakeCustomers) List(ctx context.Context, tenantID string, after *store.After, limit int) ([]store.Customer, error) {
	f.gotTenant, f.gotAfter = tenantID, after
	if len(f.all) > limit+1 {
		return f.all[:limit+1], nil
	}
	return f.all, nil
}

func get(t *testing.T, h http.Handler, url string) (*httptest.ResponseRecorder, map[string]any) {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, url, nil)
	req = req.WithContext(auth.WithTenant(req.Context(), "t_1"))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	var body map[string]any
	_ = json.Unmarshal(rec.Body.Bytes(), &body)
	return rec, body
}

func TestListCustomersPaginates(t *testing.T) {
	f := &fakeCustomers{}
	base := time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)
	for i := 0; i < 3; i++ {
		f.all = append(f.all, store.Customer{ID: fmt.Sprintf("c_%d", i), CreatedAt: base.Add(-time.Duration(i) * time.Hour)})
	}
	rec, body := get(t, listCustomers(f), "/v1/customers?limit=2")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d", rec.Code)
	}
	if n := len(body["data"].([]any)); n != 2 {
		t.Fatalf("len(data) = %d", n)
	}
	if body["next_cursor"] == nil {
		t.Fatal("expected next_cursor")
	}
	if f.gotTenant != "t_1" {
		t.Fatalf("tenant = %q", f.gotTenant)
	}
}

func TestListCustomersRejectsBadLimit(t *testing.T) {
	rec, body := get(t, listCustomers(&fakeCustomers{}), "/v1/customers?limit=500")
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d", rec.Code)
	}
	if body["error"].(map[string]any)["code"] != "invalid_parameter" {
		t.Fatalf("body = %v", body)
	}
}

func TestListCustomersRejectsBadCursor(t *testing.T) {
	rec, _ := get(t, listCustomers(&fakeCustomers{}), "/v1/customers?cursor=%%%")
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d", rec.Code)
	}
}
