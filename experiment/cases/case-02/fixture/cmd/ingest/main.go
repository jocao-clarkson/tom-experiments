package main

import (
	"context"
	"database/sql"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	_ "github.com/lib/pq"

	"github.com/tidewater/ingest/internal/config"
	"github.com/tidewater/ingest/internal/pipeline"
	"github.com/tidewater/ingest/internal/sink"
	"github.com/tidewater/ingest/internal/source"
	"github.com/tidewater/ingest/internal/transform"
)

func main() {
	log := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	clicksCfg, err := config.Load("CLICKS")
	if err != nil {
		log.Error("config", "err", err)
		os.Exit(1)
	}
	db, err := sql.Open("postgres", clicksCfg.WarehouseDSN)
	if err != nil {
		log.Error("warehouse", "err", err)
		os.Exit(1)
	}
	defer db.Close()

	src, err := source.NewKafka(clicksCfg.Topic, "ingest-clicks")
	if err != nil {
		log.Error("source", "err", err)
		os.Exit(1)
	}
	defer src.Close()

	r := &pipeline.Runner{
		Cfg:       clicksCfg,
		Src:       src,
		Sink:      &sink.PostgresWarehouse{DB: db},
		Table:     "clicks",
		DLQTable:  "clicks_dlq",
		Transform: transform.Clicks,
		Log:       log,
	}
	if err := r.Run(ctx); err != nil {
		log.Error("runner stopped", "stream", clicksCfg.Stream, "err", err)
		os.Exit(1)
	}
}
