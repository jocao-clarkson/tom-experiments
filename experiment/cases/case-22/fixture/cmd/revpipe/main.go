package main

import (
	"context"
	"log"
	"os"

	"github.com/northwind/revpipe/internal/config"
	"github.com/northwind/revpipe/internal/load"
	"github.com/northwind/revpipe/internal/pipeline"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("config: %v", err)
	}
	ctx := context.Background()
	store, err := load.NewPGStore(ctx, cfg.DSN)
	if err != nil {
		log.Fatalf("store: %v", err)
	}
	defer store.Close()

	job := "orders"
	if len(os.Args) > 1 {
		job = os.Args[1]
	}
	switch job {
	case "orders":
		err = pipeline.RunOrders(ctx, cfg, store)
	default:
		log.Fatalf("unknown job %q", job)
	}
	if err != nil {
		log.Fatalf("%s: %v", job, err)
	}
}
