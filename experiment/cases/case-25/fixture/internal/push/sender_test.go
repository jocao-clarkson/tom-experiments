package push

import (
	"context"
	"errors"
	"testing"
	"time"

	"github.com/pebbleapp/api/internal/devices"
)

type memRepo struct{ devs []devices.Device }

func (m *memRepo) Upsert(context.Context, devices.Device) error  { return nil }
func (m *memRepo) Delete(context.Context, string, string) error { return nil }
func (m *memRepo) ListForUser(_ context.Context, uid string) ([]devices.Device, error) {
	var out []devices.Device
	for _, d := range m.devs {
		if d.UserID == uid {
			out = append(out, d)
		}
	}
	return out, nil
}

type recClient struct {
	got  []string
	fail map[string]bool
}

func (c *recClient) Push(_ context.Context, d devices.Device, _ Notification) error {
	if c.fail[d.Token] {
		return errors.New("apns: bad token")
	}
	c.got = append(c.got, d.Token)
	return nil
}

func TestSendContinuesAfterDeviceFailure(t *testing.T) {
	repo := &memRepo{devs: []devices.Device{
		{Token: "a", UserID: "u1", Platform: "ios"},
		{Token: "b", UserID: "u1", Platform: "android"},
	}}
	client := &recClient{fail: map[string]bool{"a": true}}
	s := &Sender{Devices: repo, Client: client, Timeout: time.Second}
	if err := s.Send(context.Background(), "u1", Notification{Category: CategorySocial}); err != nil {
		t.Fatal(err)
	}
	if len(client.got) != 1 || client.got[0] != "b" {
		t.Fatalf("got %v", client.got)
	}
}
