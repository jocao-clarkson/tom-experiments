# Plan: Bot filtering before sessionization

## Overview

A new `etl/botfilter.py` module loads and validates the two reference lists and answers "is this event a bot, and why". `job.run` builds the filter before reading any input, splits the event stream into kept and filtered events, sessionizes the kept ones as today, and writes the filtered events with the existing `write_partition` sink. Metrics go through the existing `Metrics` counters.

## Steps

1. **Config.** Read `cfg.section("bot_filter")` in `job.run`. `enabled` defaults to `true`; when enabled, both `user_agents_path` and `ip_ranges_path` are required, and a missing key is raised as a `ValueError` naming the key. `JobConfig.section()` already exists for this.

2. **Reference parsing.** `botfilter.load_patterns(path)` and `botfilter.load_ranges(path)` strip each line and skip blanks and `#` comments. Ranges are parsed with `ipaddress.ip_network(line, strict=False)`; any `ValueError` is re-raised as `BotListError(path, line_no, line)`. Both lists are fully loaded before the job reads input, so if loading fails no `write_partition` call happens (R6, AC4).

3. **User-agent matching.** Lower-case the patterns and compile them into one alternation regex (`re.escape` per pattern, joined with `|`). Matching runs against `user_agent.lower()`. User agents repeat heavily, so the match function is wrapped in `functools.lru_cache(maxsize=200_000)`.

4. **IP matching.** Collapse ranges per IP version with `ipaddress.collapse_addresses`, then store sorted `(start_int, end_int)` tuples. A lookup parses the address once and uses `bisect` to find the candidate range. Results are memoized per IP string with `lru_cache(maxsize=500_000)`. Empty or unparseable IPs return "no match" and increment `events.unparseable_ip`, so they cannot crash the job.

5. **Classification.** `BotFilter.reason(event) -> str | None` checks the user agent first and then the IP, so an event matching both gets `user_agent` (R3).

6. **Job wiring.** In `job.run`, when enabled, wrap the event stream in a generator that classifies each event: kept events flow into `sessionize`; filtered events are appended to a list with `filter_reason` set and `ts` converted back to ISO format so the output columns match the input. `events.processed` still counts every event read. When disabled, `run` takes exactly the current code path.

7. **Outputs.** Write `sessions` first, then `filtered`, both through `write_partition`, which swaps partitions in atomically. If the second write fails, the job exits non-zero and a rerun replaces both partitions. Metrics are flushed only after both writes succeed.

8. **Metrics.** `metrics.incr("events.filtered", n, reason=...)` for each reason, using counts taken from the filtered list so AC5 holds by construction.

9. **Docs.** Add a `[bot_filter]` example to `job.toml.example` and a `README.md` note on `BotListError`.

## Test strategy

- `tests/test_botfilter.py` (new): comment and blank handling; case-insensitive UA match (AC1); IPv4 and IPv6 range matches, including the AC2 address; collapsed overlapping ranges; malformed CIDR raises `BotListError` with the line number; empty and garbage `ip` values return no match.
- `tests/test_job.py`: extend with (a) a mixed input asserting kept sessions, `filtered` rows and reasons, and `RecordingMetrics` counts (AC1, AC2, AC5); (b) a run with a malformed range file that asserts a non-zero exit and that a pre-existing `sessions` partition is unchanged (AC4); (c) `enabled = false` compared against a golden `sessions` file captured from the current version before this change (AC3).
- A local timing run on one production-sized day from the staging bucket before merging.

## Rollout and notes

- Ship with `enabled = false` for one day, then enable it and compare session counts against the previous week; we expect a drop of roughly 10 percent.
- Memory should go down slightly, since `sessionize` holds every kept event in memory and filtered events no longer go there; the filtered list itself is about a tenth of the day's events.
- The Trust team owns the lists; a bad edit will now fail the job loudly, so they have been added to the job's alert channel.
