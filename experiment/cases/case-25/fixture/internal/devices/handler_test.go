package devices

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/pebbleapp/api/internal/httpx"
)

type stubRepo struct{ saved []Device }

func (s *stubRepo) Upsert(_ context.Context, d Device) error { s.saved = append(s.saved, d); return nil }
func (s *stubRepo) Delete(context.Context, string, string) error { return nil }
func (s *stubRepo) ListForUser(context.Context, string) ([]Device, error) { return nil, nil }

func TestRegisterRejectsUnknownPlatform(t *testing.T) {
	repo := &stubRepo{}
	h := httpx.RequireUser(RegisterHandler(repo))
	req := httptest.NewRequest(http.MethodPost, "/v1/devices", strings.NewReader(`{"token":"t","platform":"web"}`))
	req.Header.Set("X-User-ID", "u1")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("status = %d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), `"code":"invalid_device"`) {
		t.Fatalf("body = %s", rec.Body.String())
	}
	if len(repo.saved) != 0 {
		t.Fatal("device should not be saved")
	}
}
