package transport

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"time"
)

type Client struct {
	endpoint string
	token    string
	http     *http.Client
	attempts int
}

func New(endpoint, token string) *Client {
	return &Client{endpoint: endpoint, token: token, http: &http.Client{Timeout: 2 * time.Minute}, attempts: 4}
}

// Upload streams the bundle to the ticket. The body is re-read from the start on each retry,
// so r must be an io.ReadSeeker.
func (c *Client) Upload(ctx context.Context, ticket string, r io.ReadSeeker, size int64) error {
	var lastErr error
	for i := 0; i < c.attempts; i++ {
		if i > 0 {
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(time.Duration(1<<i) * time.Second):
			}
			if _, err := r.Seek(0, io.SeekStart); err != nil {
				return err
			}
		}
		req, err := http.NewRequestWithContext(ctx, http.MethodPut, fmt.Sprintf("%s/%s", c.endpoint, ticket), io.NopCloser(r))
		if err != nil {
			return err
		}
		req.ContentLength = size
		req.Header.Set("Authorization", "Bearer "+c.token)
		req.Header.Set("Content-Type", "application/gzip")
		resp, err := c.http.Do(req)
		if err != nil {
			lastErr = err
			continue
		}
		resp.Body.Close()
		if resp.StatusCode < 300 {
			return nil
		}
		lastErr = fmt.Errorf("server returned %d", resp.StatusCode)
		if resp.StatusCode < 500 {
			return lastErr
		}
	}
	return lastErr
}
