package config

import (
	"os"
	"strconv"
)

type Config struct {
	HTTPAddr    string
	DatabaseURL string
	BlobBucket  string

	// MaxImagePixels caps decoded image size. Catalog product photos
	// include medium-format scans.
	MaxImagePixels int64
}

func Load() Config {
	return Config{
		HTTPAddr:       env("HTTP_ADDR", ":8080"),
		DatabaseURL:    env("DATABASE_URL", ""),
		BlobBucket:     env("BLOB_BUCKET", "fernway-media"),
		MaxImagePixels: envInt("MAX_IMAGE_PIXELS", 100_000_000),
	}
}

func env(key, def string) string {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		return v
	}
	return def
}

func envInt(key string, def int64) int64 {
	v, ok := os.LookupEnv(key)
	if !ok || v == "" {
		return def
	}
	n, err := strconv.ParseInt(v, 10, 64)
	if err != nil {
		return def
	}
	return n
}
