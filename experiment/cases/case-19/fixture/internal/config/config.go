package config

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
)

type Config struct {
	Endpoint    string   `json:"endpoint"`
	Token       string   `json:"token"`
	LogDirs     []string `json:"log_dirs"`
	MaxBundleMB int      `json:"max_bundle_mb"`
}

func DefaultPath() string {
	dir, err := os.UserConfigDir()
	if err != nil {
		return "logship.json"
	}
	return filepath.Join(dir, "logship", "config.json")
}

// Load reads the config file. A missing file yields defaults so `logship --help` works anywhere.
func Load(path string) (Config, error) {
	cfg := Config{Endpoint: "https://support.quayside.io/api/bundles", MaxBundleMB: 50}
	b, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return cfg, nil
	}
	if err != nil {
		return cfg, err
	}
	if err := json.Unmarshal(b, &cfg); err != nil {
		return cfg, err
	}
	if cfg.MaxBundleMB <= 0 {
		cfg.MaxBundleMB = 50
	}
	return cfg, nil
}
