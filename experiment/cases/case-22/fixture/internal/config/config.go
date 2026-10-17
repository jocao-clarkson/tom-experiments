package config

import (
	"fmt"
	"os"
	"strconv"
)

type Config struct {
	DSN           string
	InputDir      string
	DeadLetterDir string
	BatchSize     int
}

func Load() (Config, error) {
	cfg := Config{
		DSN:           os.Getenv("REVPIPE_DSN"),
		InputDir:      getenv("REVPIPE_INPUT_DIR", "/data/in"),
		DeadLetterDir: getenv("REVPIPE_DEADLETTER_DIR", "/data/deadletter"),
		BatchSize:     500,
	}
	if v := os.Getenv("REVPIPE_BATCH_SIZE"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil || n <= 0 {
			return cfg, fmt.Errorf("REVPIPE_BATCH_SIZE must be a positive integer")
		}
		cfg.BatchSize = n
	}
	if cfg.DSN == "" {
		return cfg, fmt.Errorf("REVPIPE_DSN is required")
	}
	return cfg, nil
}

func getenv(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}
