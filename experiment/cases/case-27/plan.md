# Plan: Daily app crash aggregates

## Overview

`daily_app_crashes` is a new job module next to `daily_sessions`, built the same way: stream one day's events with `read_events`, drop duplicates with `dedupe_by`, aggregate in memory per (platform, app_version), and write the day with `Warehouse.replace_partition`. The lookback window from `JobConfig.days()` already defaults to 3 days, which matches the late-arrival requirement. The malformed-line rule reuses the threshold logic from `daily_sessions`.

## Steps

1. **Migration.** Add `migrations/002_app_crashes_daily.sql` creating `app_crashes_daily (day DATE, platform TEXT, app_version TEXT, crash_count INTEGER, affected_users INTEGER, PRIMARY KEY (day, platform, app_version))`.

2. **Shared rejection type.** Move `PartitionRejected` and `MAX_MALFORMED_RATIO` from `etl/jobs/daily_sessions.py` into a small `etl/jobs/common.py` and import them from both jobs. `daily_sessions` keeps the same names via import, so behaviour and its tests are unchanged.

3. **Day builder.** In `etl/jobs/daily_app_crashes.py`, add `build_day(storage, day) -> (rows, stats)`. It iterates `dedupe_by(read_events(storage, day, stats))`, keeps events with `type == "crash"`, normalises `platform` and `app_version` with `(e.get(k) or "unknown")`, and accumulates `crash_count` in a `defaultdict(int)` and user ids in a `defaultdict(set)` keyed by `(platform, app_version)`.

4. **Malformed check.** After the iterator is exhausted, raise `PartitionRejected` if `stats.malformed_ratio > MAX_MALFORMED_RATIO`. Because the check runs before any write, a rejected day never reaches `replace_partition` and keeps its previous rows (R7).

5. **Rows.** Emit rows sorted by `(platform, app_version)` as `(day.isoformat(), platform, version, crash_count, len(users))`.

6. **Run loop.** `run(cfg, storage, wh) -> bool` mirrors `daily_sessions.run`: loop over `cfg.days()`, catch `PartitionRejected` per day (log, emit `partition_rejected`, set `ok = False`, continue), otherwise `replace_partition("app_crashes_daily", ...)` and emit `rows_written` and `malformed_lines` tagged `job=daily_app_crashes`. The CLI already maps `False` to exit code 1.

7. **Registration.** Add `"daily_app_crashes": daily_app_crashes.run` to `JOBS` in `etl/jobs/__init__.py`, which makes it available to `etl` and its argparse choices.

8. **Memory check.** Distinct-user sets are the largest structure. At 4 million crash events a day, the distinct users are well under that and spread over a few hundred (platform, version) keys, so they stay within the worker's budget. `dedupe_by`'s seen-set holds up to 4 million `event_id` strings (a few hundred MB at worst), which is the same pattern `daily_sessions` already runs on far higher volume.

9. **Scheduling.** Add the job to the scheduler config next to `daily_sessions` with the same start time; the two read the same partitions but write different tables.

## Test strategy

New `tests/test_daily_app_crashes.py`, using the `storage`, `write_events` and `warehouse` fixtures from `tests/conftest.py`. The `warehouse` fixture gains the `app_crashes_daily` table.

- AC1: three crash events (two users) plus a `session_start` that must be ignored.
- AC2: a crash without `app_version` lands under `"unknown"`.
- R5: a repeated `event_id` counts once.
- AC3: run twice, assert identical rows.
- AC4: with `lookback=3` and `run_date` such that D is two days back, write D's first event, run, then add a second part file to D and run again; the count goes up.
- AC5: two days in the window, one with 2% malformed lines. Assert that day's rows are unchanged, the other day is updated, and `run` returns `False`.
- Existing `tests/test_daily_sessions.py` is run unchanged to confirm the step-2 refactor.

## Rollout

- Apply migration 002, deploy, and let the first scheduled run fill the last 3 days.
- Compare one week of `crash_count` against the vendor dashboard; small differences from vendor-side sampling are expected and noted for the mobile team.
