# Plan: Purchases stream ingestion

## Overview

Purchases differ from clicks in two ways: amounts need decimal parsing, and rows can be corrected by later revisions. To keep the purchase-specific logic in one place, we add a `purchases` package with its own transform, writer and loop, and reuse `config.Load` and the `source.Source` interface. Clicks keep running through the existing `pipeline.Runner` unchanged.

## Steps

1. **Config** (`cmd/ingest/main.go`). Call `config.Load("PURCHASES")` at startup and add `PURCHASES_TOPIC=purchases.v2` to the deployment env. The defaults (batch size 500, 2s flush) apply.

2. **Transform** (`internal/transform/purchases.go`, new). Add `Purchases(raw [][]byte) ([]sink.Row, []transform.Rejected)`, following the shape of `Clicks`. Payloads that fail to decode or have an empty `event_id` are rejected as `missing_event_id`. Parse `amount` with `strconv.ParseFloat` and convert with `int64(math.Round(f * 100))`; a parse error is `invalid_amount`. Upper-case `currency` and reject anything that is not three ASCII letters as `invalid_currency`. `occurred_at` is parsed as RFC 3339 and converted to UTC.

3. **Writer** (`internal/purchases/writer.go`, new). Add a `Writer` holding a `*sql.DB` with a `WritePurchases(ctx, rows)` method. It opens one transaction per batch and executes, per row, `INSERT INTO purchases (...) VALUES (...) ON CONFLICT (event_id) DO UPDATE SET` every non-key column to `EXCLUDED`, so a corrected purchase replaces the stored row. It also has `WriteDLQ(ctx, rows)` for `purchases_dlq`.

4. **Loop** (`internal/purchases/loop.go`, new). `Run(ctx)` polls `cfg.BatchSize` messages from a `source.Source`, runs the transform and calls the writer.

5. **Offset handling** (`internal/purchases/loop.go`). After each poll and transform, commit the polled messages so that the consumer group's lag metric reflects real progress, then hand the rows to the writer.

6. **DLQ** (`internal/purchases/loop.go`). Rejected records are written with `WriteDLQ` with `event_id` (when present), `stream`, `reason` and `payload` columns, in the same iteration as the good rows.

7. **Write failures** (`internal/purchases/loop.go`). If `WritePurchases` returns an error, the loop sleeps 2 seconds and retries the same batch until it succeeds, so that no purchase is ever dropped. Offsets are not committed until the write succeeds.

8. **Metrics** (`internal/purchases/loop.go`). After each batch, call `metrics.NewCounter("rows_ingested").Add(cfg.Stream, n)` with the number of rows written.

9. **Wiring** (`cmd/ingest/main.go`). Create the source with `source.NewKafka(cfg.Topic, "ingest-purchases")` and start `purchases.Run` in its own goroutine next to the clicks runner, sharing the warehouse `*sql.DB`.

10. **Shutdown** (`cmd/ingest/main.go`). Both streams use the signal context already created in `main`. `purchases.Run` returns once the current batch has finished, and `main` waits for it before closing the database.

## Test strategy

- `internal/transform/purchases_test.go`: table-driven tests for amount parsing (`"19.99"`, `"0.10"`, `"12.3x"`, empty), currency normalisation (`"usd"`, `"US"`), undecodable payloads, and each reason code (AC3, AC5).
- `internal/purchases/loop_test.go`: drive `Run` with a fake source modelled on the `fakeSource` in `runner_test.go` and a fake writer. Check that rejected rows go to the DLQ, that rows are written in batch-size chunks, and that a failing writer leaves nothing committed (AC4).
- Revision handling and replay (AC1, AC2) are covered by the fake writer recording calls: the test asserts that a replayed batch is passed to the writer again, and that revision 1 delivered after revision 2 reaches the writer unchanged.
- Config: a small test that `config.Load("PURCHASES")` picks up `PURCHASES_BATCH_SIZE` and rejects a non-numeric value, mirroring how the clicks stream is configured.
- The existing `runner_test.go` is unchanged, and all tests run in the existing CI job.

## Rollout and notes

- Deploy with `PURCHASES_TOPIC` set and the consumer group starting from `latest`. Backfill is out of scope.
- Watch consumer lag and `rows_ingested` for the first day; the dashboard alert threshold is 2 minutes.
- Runbook: add a "purchases ingest" section to the ingest on-call page covering how to pause the stream (scale the deployment's purchases worker to zero via `PURCHASES_ENABLED=false`) and how to read the DLQ by reason code.
- Purchases volume is about 1/10 of clicks today, so a single goroutine is sufficient. If needed we can shard by partition later.
- Commerce has confirmed that the `purchases.v2` schema is stable for this quarter.
