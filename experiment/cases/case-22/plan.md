# Plan: Refunds feed and net daily revenue

## Overview

Add a `refunds` job beside the existing `orders` job. It reads each refunds file, validates and converts amounts, looks up the parent order, upserts valid refunds, writes rejects to a dead-letter CSV, and updates the new `refunds_minor` and `net_minor` columns on `daily_revenue`. The job reuses the config loader, the CSV reader, and the `Store` abstraction so it runs through the same entry point and connection pool.

## Steps

1. **Migration.** Add `migrations/0003_refunds.sql` creating `refunds` (primary key `refund_id`) and adding `refunds_minor BIGINT NOT NULL DEFAULT 0` and `net_minor BIGINT NOT NULL DEFAULT 0` to `daily_revenue`.

2. **Entry point.** Add a `"refunds"` case to the job switch in `cmd/revpipe/main.go` that calls `pipeline.RunRefunds(ctx, cfg, store)`.

3. **Amount parsing.** Add `internal/refunds/amount.go` with `toMinor(amount, currency string) (int64, error)`. It parses with `strconv.ParseFloat`, multiplies by 100, and rounds with `math.Round`, which handles the provider's values like `"19.99"` or `"5"`. Values with more than two decimal places are rejected as `invalid_amount`.

4. **Store methods.** Extend `load.Store` and `PGStore` in `internal/load/store.go` with `UpsertRefunds(ctx, []Refund)` (ON CONFLICT on `refund_id`, mirroring `UpsertOrders`) and `OrderExists(ctx, ids []string) (map[string]bool, error)`, which checks a batch of order ids in one query.

5. **Reading and ordering.** In `internal/pipeline/refunds.go`, open each file with `extract.Open` and read all records into a slice, then sort by `refunded_at`. Applying refunds in day order keeps the daily aggregate updates sequential and makes the run log easy to follow.

6. **Batch processing.** Walk the sorted slice in chunks of `cfg.BatchSize`. For each chunk, call `OrderExists`, split into known and unknown, upsert the known refunds, and send unknown ones to the dead-letter writer.

7. **Daily aggregates.** After each chunk is upserted, add the chunk's totals per (day, currency) with `UPDATE daily_revenue SET refunds_minor = refunds_minor + $1, net_minor = gross_minor - (refunds_minor + $1)`, inserting the row first if the day has no orders yet. This keeps the aggregate current while the job runs.

8. **Dead-letter writer.** Add `internal/refunds/deadletter.go` that creates `refunds-<run date>.csv` under `cfg.DeadLetterDir` and writes `refund_id, deadletter_reason`. Keeping the file to identifiers avoids copying customer data into a directory other teams can read.

9. **Logging.** For each dead-lettered refund, log `log.Printf("deadletter refund %v: %s", rec, reason)` so the on-call engineer can see the full row without opening the file. At the end of each file, log counts of loaded, dead-lettered, and invalid rows.

10. **Docs.** Document the job, its environment variables, and the dead-letter file format in the repository README.

## Test strategy

- `internal/refunds/amount_test.go`: table tests for `"19.99"`, `"5"`, `"0.10"`, and the rejected `"12.345"` (AC1).
- `internal/pipeline/refunds_test.go`: using a fake store like the one in `orders_test.go`, a small CSV with one known and one unknown order checks that only the known refund is upserted and the unknown one appears in the dead-letter file (AC2).
- The aggregate SQL is reviewed by hand against a staging snapshot before the first production run.
- Performance (AC4) is expected to be fine given batched upserts and a single lookup query per chunk; we'll watch the first production run.

## Rollout

- Apply migration 0003 before deploying the binary.
- Schedule the job in the batch scheduler 30 minutes after the orders job, so most parent orders exist.
- First week: compare `net_minor` against finance's spreadsheet for three sample days.
- The payments support team is told where the dead-letter file lands and how to read it.
