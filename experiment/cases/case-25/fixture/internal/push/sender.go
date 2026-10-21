package push

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/pebbleapp/api/internal/devices"
	"github.com/pebbleapp/api/internal/metrics"
)

type Category string

const (
	CategorySecurity  Category = "security"
	CategorySocial    Category = "social"
	CategoryMarketing Category = "marketing"
	CategoryReminders Category = "reminders"
)

type Notification struct {
	Category Category
	Title    string
	Body     string
	Data     map[string]string
}

// Client delivers to APNs / FCM. Implementations do not retry.
type Client interface {
	Push(ctx context.Context, d devices.Device, n Notification) error
}

// GatewayClient posts to the internal push gateway, which holds the APNs and
// FCM credentials.
type GatewayClient struct {
	URL  string
	HTTP *http.Client
}

func (g *GatewayClient) Push(ctx context.Context, d devices.Device, n Notification) error {
	body, err := json.Marshal(map[string]any{
		"token": d.Token, "platform": d.Platform, "category": n.Category,
		"title": n.Title, "body": n.Body, "data": n.Data,
	})
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, g.URL+"/v1/push", bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := g.HTTP.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		return fmt.Errorf("push gateway: status %d", resp.StatusCode)
	}
	return nil
}

type Sender struct {
	Devices devices.Repo
	Client  Client
	Timeout time.Duration
}

// Send delivers n to every registered device of userID. Per-device failures
// are logged and counted; they do not abort delivery to other devices.
func (s *Sender) Send(ctx context.Context, userID string, n Notification) error {
	devs, err := s.Devices.ListForUser(ctx, userID)
	if err != nil {
		return err
	}
	for _, d := range devs {
		pctx, cancel := context.WithTimeout(ctx, s.Timeout)
		err := s.Client.Push(pctx, d, n)
		cancel()
		if err != nil {
			metrics.Inc("push_failed_total", map[string]string{"platform": d.Platform})
			log.Printf("push to %s device failed: %v", d.Platform, err)
			continue
		}
		metrics.Inc("push_sent_total", map[string]string{"category": string(n.Category)})
	}
	return nil
}
