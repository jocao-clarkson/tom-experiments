package config

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"runtime"
)

type Config struct {
	Endpoint    string   `json:"endpoint"`
	Token       string   `json:"token"`
	LogDirs     []string `json:"log_dirs"`
	SystemLog   string   `json:"system_log"`
	MaxBundleMB int      `json:"max_bundle_mb"`
}

func DefaultPath() string {
	dir, err := os.UserConfigDir()
	if err != nil {
		return "logship.json"
	}
	return filepath.Join(dir, "logship", "config.json")
}

func defaultSystemLog() string {
	switch runtime.GOOS {
	case "linux":
		return "/var/log/syslog"
	case "darwin":
		return "/var/log/system.log"
	}
	return ""
}

// Load reads the config file. A missing file yields defaults so `logship --help` works anywhere.
func Load(path string) (Config, error) {
	cfg := Config{
		Endpoint:    "https://support.quayside.io/api/bundles",
		SystemLog:   defaultSystemLog(),
		MaxBundleMB: 50,
	}
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
