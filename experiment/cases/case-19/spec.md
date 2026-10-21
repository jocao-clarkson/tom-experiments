# Spec: `logship collect`

**Team:** Support Tooling · **Users:** customers' operators, guided by our support engineers

## Goal

Support asks customers for logs daily, and customers send whatever they find, often unredacted and often far too much. `logship collect` will gather the relevant logs on the customer's machine, scrub secrets with the same rules `logship` already uses, and produce a bounded bundle that can optionally be uploaded to the support ticket.

## Functional requirements

- **R1.** `logship collect [--since 24h] [--include-system] [--upload --ticket ID] [--dry-run]` collects regular files under each directory in `log_dirs` (from config) whose modification time is within `--since` (default `24h`). `--include-system` also adds `/var/log/syslog` on Linux or `/var/log/system.log` on macOS when present.
- **R2.** Every line of every collected file is redacted with the existing `internal/redact` rules before it goes into the bundle. No unredacted byte may be written to disk.
- **R3.** The bundle is `logship-<hostname>-<UTC timestamp>.tar.gz` in the current directory. If the redacted total exceeds `max_bundle_mb` (config, default 50), drop the **oldest** files until it fits and print a warning naming the dropped files.
- **R4.** `--upload --ticket ID` uploads the finished bundle through the existing upload path, and the summary then also reports the ticket ID and the number of bytes uploaded.
- **R5.** Exit codes follow the existing contract: `0` success, `2` usage error, `3` partial (one or more files could not be read and were skipped), `4` upload failed.
- **R6.** The final summary (files included, files skipped with reason, files dropped for size, redaction count, bundle path, and upload details) respects the global `--output text|json` flag.
- **R7.** `--dry-run` prints the files that would be collected and writes nothing.

## Acceptance criteria

- **AC1.** A log containing `password=hunter2` and an email address appears in the bundle with both masked.
- **AC2.** With three files totalling more than the cap, the oldest is dropped, a warning is printed, and the bundle fits.
- **AC3.** An unreadable file is listed as skipped and the command exits 3.
- **AC4.** With `--include-system` on Linux, the system log is included when readable.
- **AC5.** `--output json` produces one JSON object with the summary fields; with `--upload`, it includes the ticket ID and uploaded bytes.

## Non-functional constraints

- Memory use must stay bounded regardless of log size; individual system logs can be several GB.
- Never require or request elevated privileges.
- CI runs `go test ./...` unprivileged on Linux, macOS and Windows runners; tests must not depend on the host's own log files.
- No new module dependencies.

## Out of scope

- Collecting from journald or Windows Event Log.
- Changing redaction rules.
- Resumable uploads.
