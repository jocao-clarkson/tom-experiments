# Spec: Bot traffic filtering in the sessions job

**Team:** Growth Analytics · **Job:** `sessions-job` (daily)

## Goal

Crawlers and uptime monitors make up an estimated 8 to 12 percent of raw clickstream events and inflate session counts, especially single-pageview sessions. Marketing has asked that the daily `sessions` dataset exclude known bots. We will filter events against two reference lists maintained by the Trust team before sessionization, and keep the excluded events in a side dataset so the filter can be audited.

## Functional requirements

- **R1.** Load two reference files whose paths come from the `[bot_filter]` section of `job.toml`:
  - `user_agents_path`: one pattern per line; an event matches if its `user_agent` contains the pattern, case-insensitively. Blank lines and lines starting with `#` are ignored.
  - `ip_ranges_path`: one IPv4 or IPv6 CIDR per line, same comment rules.
- **R2.** Events matching either list are excluded from sessionization.
- **R3.** Excluded events are written to the `filtered` dataset for the same day with all original columns plus `filter_reason`, which is `user_agent` or `ip_range`. If both match, use `user_agent`.
- **R4.** Emit counter `events.filtered` tagged with `reason`, in addition to the existing `events.processed` (which keeps counting all events read).
- **R5.** `[bot_filter] enabled` (default `true`). When `false`, the job's output must be identical to today's and no `filtered` partition is written.
- **R6.** If filtering is enabled and either reference file is missing or contains an invalid line, the job fails **before writing any output**. Silently running unfiltered is not acceptable.

## Acceptance criteria

- **AC1.** An event with user agent `Mozilla/5.0 (compatible; Googlebot/2.1)` and pattern `googlebot` is excluded and appears in `filtered` with reason `user_agent`.
- **AC2.** An event from `66.249.70.12` with range `66.249.64.0/19` is excluded with reason `ip_range`.
- **AC3.** With `enabled = false`, the `sessions` output matches a run on the current version byte for byte.
- **AC4.** A malformed CIDR line makes the job exit non-zero and leaves existing output for that day untouched.
- **AC5.** `events.filtered` counts per reason match the rows in `filtered`.

## Non-functional constraints

- Daily volume is about 40 million events; the job must still finish within its 1-hour slot. The lists are small today (~600 patterns, ~1,500 ranges) but may grow.
- No new third-party dependencies.
- Events with a missing or unparseable `ip` must not crash the job.

## Out of scope

- Behavioural or ML-based bot detection.
- Maintaining or fetching the reference lists.
- Re-processing historical days.
