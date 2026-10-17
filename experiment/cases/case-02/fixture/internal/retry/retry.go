package retry

import (
	"context"
	"math/rand"
	"time"
)

// Do calls fn up to attempts times with exponential backoff and full jitter.
// It stops early if ctx is cancelled and returns the last error from fn.
func Do(ctx context.Context, attempts int, base time.Duration, fn func(context.Context) error) error {
	var err error
	for i := 0; i < attempts; i++ {
		if err = fn(ctx); err == nil {
			return nil
		}
		if i == attempts-1 {
			break
		}
		backoff := base << i
		sleep := time.Duration(rand.Int63n(int64(backoff) + 1))
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(sleep):
		}
	}
	return err
}
