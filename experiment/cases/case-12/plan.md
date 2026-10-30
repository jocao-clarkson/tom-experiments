# Plan: amount_usd in events_clean, with 90-day backfill

## Overview

Conversion happens in the transform stage, using a per-partition rate map loaded with one query from `ref.fx_rates_daily`. The nightly path keeps flowing through `pipeline/runner.py`. The backfill is its own job, exposed as `events-pipeline backfill`, with its own progress file so it can be stopped and resumed independently of the nightly schedule.

## Steps

1. **Schema migration.** Add `migrations/0007_amount_usd.sql`: `ALTER TABLE analytics.events_clean ADD COLUMN amount_usd NUMERIC(18,2)`. The quarantine table stores the raw event plus `reason`, so it needs no change.

2. **Rate loading.** Add `pipeline/fx.py` with `load_rates(wh, partition) -> dict[str, Decimal]`. It makes a single `Warehouse.query` call, `SELECT currency, usd_rate FROM ref.fx_rates_daily WHERE rate_date = %s`, with the partition date as the parameter, and returns a `{currency: usd_rate}` map. This satisfies R5.

3. **Transform.** Extend `transform.normalize(events, rates=None)`. When `rates` is given, each clean row with a non-null `amount` gets `amount_usd = (amount * rates[currency]).quantize(Decimal("0.01"), ROUND_HALF_EVEN)`; rows with a null `amount` get `amount_usd = None`. The `rates=None` default leaves existing callers unchanged.

4. **Missing rates.** In `normalize`, a row whose currency is not in `rates` is moved to the quarantine list with `reason = f"missing_fx_rate:{currency}"`, in the same `name:detail` form as the existing `missing_fields:` reasons. Nothing is converted with a substitute rate.

5. **Nightly wiring.** In `runner.process_partition`, call `fx.load_rates(wh, partition)` and pass the map to `normalize`. `runner.run` is otherwise unchanged.

6. **Partition summary.** `process_partition` adds `missing_fx_rate`, the number of quarantined rows with that reason, to the summary dict it returns, next to `loaded` and `quarantined`. `run` logs it with the rest of the summary after each partition, which covers R6 and AC4.

7. **Backfill job.** Add `scripts/backfill_fx.py` with `main(cfg, wh, days, today)`. It builds the list of the `days` partitions ending yesterday, sorted newest first, and for each one reads events with `extract.read_partition`, loads rates with `fx.load_rates`, runs `transform.normalize`, writes both tables with `Warehouse.replace_partition`, and logs the loaded and quarantined counts. Its progress is tracked separately (step 8).

8. **Restartability.** After each partition the backfill writes `{"last_done": partition}` to `state/backfill_progress.json`. On start it reads that file and skips every partition on or before `last_done`; `--from-scratch` deletes the file first.

9. **CLI.** Turn `pipeline/cli.py` into a subcommand parser: with no subcommand it runs the nightly job exactly as today, and `backfill` takes `--days` (default 90, validated 1 to 120) and `--from-scratch`, opens the warehouse connection and calls `scripts.backfill_fx.main`.

10. **Runbook.** Update `docs/runbook.md` with backfill usage, expected duration, how to resume after a stop, and how to read the new summary field.

## Test strategy

All tests run in CI against in-memory fakes; none need warehouse access.

- `tests/test_fx.py` (new): `load_rates` issues exactly one query and returns `Decimal` values (R5); conversion rounding for EUR including a half-even edge case such as `0.125 -> 0.12` (AC1).
- `tests/test_transform.py`: add a missing-rate case asserting the row is absent from the clean list and its reason starts with `missing_fx_rate` (AC2), and a null-amount case that expects `amount_usd is None`.
- `tests/test_backfill.py` (new): a `RatesWarehouse` subclass of `FakeWarehouse`, defined in the test module, returns canned rates from `query`. The test runs the backfill twice over three partitions and asserts identical row counts in both tables (AC3) and checks that partitions are processed newest first (R3).
- `tests/test_runner.py`: add a case asserting that the `process_partition` summary contains `missing_fx_rate` with the right count (AC4).
- The existing `tests/test_runner.py` and `tests/test_transform.py` cases keep passing unchanged because `normalize` defaults `rates` to `None`.

## Rollout and notes

- Deploy the migration and the nightly change first and let one nightly run complete with `amount_usd` populated.
- Start the backfill from the ops box the following evening, around 20:00 UTC. At about 6 minutes per partition the 90-day run takes roughly 9 hours and finishes the next morning.
- Finance Analytics switches dashboards to `amount_usd` once the backfill logs its final partition.
- `amount_usd` is nullable and nothing is renamed or dropped, so dashboards keep reading `amount` until they switch. Rolling back the code leaves the column in place and harmless.
