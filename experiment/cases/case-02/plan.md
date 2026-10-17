# Plan: Purchases stream ingestion

## Overview

Purchases differ from clicks in two ways: amounts need decimal parsing, and rows can be corrected by later revisions. To keep the purchase-specific logic in one place, we add a `purchases` package with its own transform, writer and loop, and reuse `config.Load` and the `source.Source` interface. Clicks keep running through the existing `pipeline.Runner` unchanged.

## Steps

1. **Config** (`cmd/ingest/main.go`). Call `config.Load("PURCHASES")` at startup and add `PURCHASES_TOPIC=purchases.v2` to the deployment env. The defaults (batch size 500, 2s flush) apply.

2. **Transform** (`internal/transform/purchases.go`, new). Add `Purchases(raw [][]byte) ([]sink.Row, []transform.Rejected)`, following the shape of `Clicks`. Parse `amount` with `strconv.ParseFloat` and convert with `int64(math.Round(f * 100))`. Upper-case `currency` and reject anything that is not three ASCII letters. Reason codes: `missing_event_id`, `invalid_amount`, `invalid_currency`, plus `malformed_json` for undecodable payloads.

3. **Writer** (`internal/purchases/writer.go`, new). Add a `Writer` holding a `*sql.DB` and a `WritePurchases(ctx, rows)` method. It builds a multi-row `INSERT INTO purchases (...) VALUES (...), (...)` so a 500-row batch is one round trip, which we need at 5k events/s. It also has `WriteDLQ(ctx, rows)` for `purchases_dlq`.

4. **Loop** (`internal/purchases/loop.go`, new). `Run(ctx)` polls `cfg.BatchSize` messages, runs the transform and calls the writer.

5. **Offset handling** (`internal/purchases/loop.go`). After each poll and transform, commit the polled messages so that the consumer group's lag metric reflects real progress, then hand the rows to the writer.

6. **DLQ** (`internal/purchases/loop.go`). Rejected records are written with `WriteDLQ` with `stream`, `reason` and `payload` columns, in the same iteration as the good rows.

7. **Write failures** (`internal/purchases/loop.go`). If `WritePurchases` returns an error, the loop sleeps 2 seconds and retries the same batch until it succeeds, so that no purchase is ever dropped. Offsets are not committed until the write succeeds.

8. **Metrics** (`internal/purchases/loop.go`). Increment `rows_ingested` by the number of rows written, using `metrics.NewCounter`.

9. **Wiring** (`cmd/ingest/main.go`). Start `purchases.Run` in its own goroutine next to the clicks runner, sharing the warehouse `*sql.DB`.

10. **CI** (`.github/workflows/ci.yml`). Add an `integration` job with a `postgres:16` service container and run `go test -tags=integration ./internal/purchases/...` against it, so the writer's SQL is exercised against a real database.

## Test strategy

- `internal/transform/purchases_test.go`: table-driven tests for amount parsing (`"19.99"`, `"0.10"`, `"12.3x"`, empty), currency normalisation, and each reason code (AC3, AC5).
- `internal/purchases/loop_test.go`: drive `Run` with the existing `fakeSource` pattern and a fake writer. Check that rejected rows go to the DLQ and that rows are written in batch-size chunks.
- Revision handling and replay (AC1, AC2) are covered by the fake writer recording calls: the test asserts that a replayed batch is passed to the writer again.
- `internal/purchases/writer_integration_test.go` (build tag `integration`): runs against the Postgres service from step 10 and inserts a batch.
- Config: a small test that `config.Load("PURCHASES")` picks up `PURCHASES_BATCH_SIZE` and rejects a non-numeric value, mirroring how the clicks stream is configured.
- The existing `runner_test.go` is unchanged.

## Rollout and notes

- Deploy with `PURCHASES_TOPIC` set and the consumer group starting from `latest`. Backfill is out of scope.
- Watch consumer lag and `rows_ingested` for the first day; the dashboard alert threshold is 2 minutes.
- Runbook: add a "purchases ingest" section to the ingest on-call page covering how to pause the stream (scale the deployment's purchases worker to zero via `PURCHASES_ENABLED=false`) and how to read the DLQ by reason code.
- Purchases volume is about 1/10 of clicks today, so a single goroutine is sufficient. If needed we can shard by partition later.
- The writer is purchase-specific for now. If a third stream needs revisions, we can fold it back into `sink`.
