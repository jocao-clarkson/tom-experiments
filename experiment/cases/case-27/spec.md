# Spec: Daily app crash aggregates

## Goal

The mobile team tracks crashes per release from a vendor dashboard that only keeps 30 days and can't be joined to our other telemetry. Build a daily warehouse table of crash counts per app version and platform from the crash events we already collect, so release health can be tracked in the same place as sessions.

## Functional requirements

- **R1.** Add an ETL job `daily_app_crashes` runnable as `etl daily_app_crashes`, scheduled like the existing jobs.
- **R2.** Input: events with `type == "crash"` from the existing telemetry event partitions, which are keyed by the event's own day (late uploads are appended to the older partition). Relevant fields: `event_id`, `user_id`, `platform`, `app_version`.
- **R3.** Output table `app_crashes_daily(day, platform, app_version, crash_count, affected_users)`, where `affected_users` is the number of distinct `user_id`s with at least one crash that day for that platform and version.
- **R4.** Events with a missing or empty `platform` or `app_version` are counted under `"unknown"` rather than dropped.
- **R5.** Duplicate deliveries (same `event_id`) are counted once.
- **R6.** Crash events can arrive up to 3 days late. Each run must rebuild the most recent 3 days so late events are included.
- **R7.** If more than 1% of a day's lines are malformed, that day's partition is not rewritten (previous data is kept), the remaining days are still processed, and the job exits non-zero.
- **R8.** Emit the `rows_written` and `malformed_lines` metrics, tagged with the job name, as the other jobs do.

## Acceptance criteria

- **AC1.** Given two crashes from one user and one from another on iOS 5.3.0, the row for that day shows `crash_count = 3, affected_users = 2`.
- **AC2.** A crash with no `app_version` appears under `app_version = "unknown"`.
- **AC3.** Re-running the job for the same day yields identical rows.
- **AC4.** A crash for day D written into D's partition two days late, after a run has already processed D, is included after the next run.
- **AC5.** With 2% malformed lines on one day, that day keeps its previous rows, other days are updated, and the exit code is 1.

## Non-functional constraints

- The job runs on the shared ETL worker (2 GB RAM). Peak daily volume is about 4 million crash events.
- No new dependencies.
- The output table is created through the normal migrations folder.

## Out of scope

- Symbolication or stack-trace grouping.
- Alerting on crash spikes.
- Backfilling history older than the lookback window.
- Joining with session counts to compute crash-free rates (follow-up).
