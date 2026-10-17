# Plan: amount_usd in events_clean, with 90-day backfill

## Overview

Conversion happens in the transform stage, using a per-partition rate map loaded once from `ref.fx_rates_daily`. The nightly path keeps flowing through `pipeline/runner.py`. The backfill is a separate job so it can be run, stopped and restarted without interfering with the nightly schedule, and it is exposed as `events-pipeline backfill`.

## Steps

1. **Schema migration.** Add `migrations/0007_amount_usd.sql`: `ALTER TABLE analytics.events_clean ADD COLUMN amount_usd NUMERIC(18,2)`. The quarantine table stores the raw event plus `reason`, so it needs no change.

2. **Rate loading.** Add `pipeline/fx.py` with `load_rates(wh, partition) -> dict[str, Decimal]`, using one `Warehouse.query` call: `SELECT currency, usd_rate FROM ref.fx_rates_daily WHERE rate_date = %s`. This satisfies R5.

3. **Missing-rate fallback.** Treasury occasionally publishes a day late, so when a currency is missing for the event date, `fx.py` falls back to the most recent rate within the previous 3 days (one extra query per partition, only when needed). Rows still missing after the fallback are quarantined with `reason = "missing_fx_rate"`.

4. **Transform.** Extend `transform.normalize(events, rates=None)` to compute `amount_usd` with `Decimal.quantize(Decimal("0.01"), ROUND_HALF_EVEN)` and route missing-rate rows to the quarantine list. The `rates=None` default keeps existing callers and tests working.

5. **Nightly wiring.** In `runner.process_partition`, call `fx.load_rates` and pass the result to `normalize`. The returned summary continues to report `loaded` and `quarantined`.

6. **Backfill job.** Add `scripts/backfill_fx.py`. It computes the last N partitions (default 90, capped at 120), sorts them newest first, and for each one runs `extract.read_partition`, `fx.load_rates`, `transform.normalize` and `Warehouse.replace_partition` for both tables directly, logging progress as it goes. It does not use `run_lock` or the checkpoint, so it never blocks the nightly run. Because every write is a whole-partition replace, a backfill and the nightly job touching the same day is harmless: whichever finishes last wins, with the same data.

7. **Restartability.** The backfill writes its own progress file, `state/backfill_progress.json`, after each partition, and skips completed partitions on restart unless `--from-scratch` is passed.

8. **CLI.** Add a `backfill` subparser in `pipeline/cli.py` with `--days` (validated 1 to 120) that calls `scripts.backfill_fx.main`.

9. **Runbook.** Update `docs/runbook.md` with backfill usage, the expected duration (~6 minutes per partition), and how to resume.

## Test strategy

- `tests/test_fx.py` (new): rounding (AC1) including a half-even edge case, and fallback to a prior day's rate.
- `tests/test_transform.py`: extend with a missing-rate case that asserts the row is quarantined with `missing_fx_rate` (AC2) and a null-amount case.
- `tests/integration/test_fx_warehouse.py` (new): runs `process_partition` against the staging warehouse for one recent partition and checks that `amount_usd` is populated for EUR and GBP. It runs in the CI pipeline using the staging DSN so that the real SQL is exercised.
- AC3 (idempotent reruns) is covered by the replace-partition design; we will also confirm it by hand on staging by running the backfill twice and comparing counts.

## Rollout and notes

- Deploy the migration and the nightly change first and let one nightly run complete; then start the backfill manually from the ops box.
- At ~6 minutes per partition the 90-day backfill takes about 9 hours, so we expect it to overlap at least one nightly window.
- Finance Analytics will switch dashboards to `amount_usd` once the backfill reports done.
- `amount_usd` is nullable and nothing is renamed or dropped, so existing dashboards keep reading `amount` until they switch; rolling back the code leaves the column in place and harmless.
- Existing `tests/test_runner.py` and `tests/test_transform.py` cases keep passing unchanged because `normalize` defaults `rates` to `None`.
