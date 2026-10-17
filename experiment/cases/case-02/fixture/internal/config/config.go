package config

import (
	"fmt"
	"os"
	"strconv"
	"time"
)

// Config holds runtime settings for an ingest stream. Every stream reads the
// same keys, prefixed by the stream name (for example CLICKS_BATCH_SIZE).
type Config struct {
	Stream        string
	Topic         string
	BatchSize     int
	FlushInterval time.Duration
	WriteAttempts int
	RetryBase     time.Duration
	WarehouseDSN  string
}

func Load(stream string) (Config, error) {
	c := Config{
		Stream:        stream,
		BatchSize:     500,
		FlushInterval: 2 * time.Second,
		WriteAttempts: 5,
		RetryBase:     200 * time.Millisecond,
	}
	c.Topic = env(stream, "TOPIC", "")
	c.WarehouseDSN = os.Getenv("WAREHOUSE_DSN")
	if v := env(stream, "BATCH_SIZE", ""); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil || n <= 0 {
			return c, fmt.Errorf("config: invalid %s_BATCH_SIZE %q", stream, v)
		}
		c.BatchSize = n
	}
	if v := env(stream, "WRITE_ATTEMPTS", ""); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil || n <= 0 {
			return c, fmt.Errorf("config: invalid %s_WRITE_ATTEMPTS %q", stream, v)
		}
		c.WriteAttempts = n
	}
	if c.Topic == "" {
		return c, fmt.Errorf("config: %s_TOPIC is required", stream)
	}
	return c, nil
}

func env(stream, key, def string) string {
	if v, ok := os.LookupEnv(stream + "_" + key); ok {
		return v
	}
	return def
}
