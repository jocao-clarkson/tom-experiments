# Spec: `logship prune`

## Goal

Field engineers' laptops fill up with old log bundles because nothing ever removes them. Add a `prune` command that deletes local bundles past a given age, safely and predictably, so it can be run by hand or from a user's own cron.

## Functional requirements

- **R1.** New subcommand `logship prune --older-than <duration>`. `--older-than` is required and uses the same duration syntax as the rest of the tool (`30m`, `12h`, `7d`, `2w`).
- **R2.** A bundle's age is measured from the timestamp in its file name, not the file's modification time.
- **R3.** By default only bundles that have been uploaded are eligible. `--include-pending` also makes not-yet-uploaded bundles eligible.
- **R4.** Deleting a bundle also deletes its `.uploaded` marker, if present.
- **R5.** `--dry-run` reports what would be deleted without deleting anything.
- **R6.** Human output lists each deleted (or would-be-deleted) bundle and ends with a summary line: count and total size freed. `--json` prints a single object `{"deleted": [names], "bytes_freed": int, "dry_run": bool, "failed": [names]}`. `--quiet` prints only errors.
- **R7.** Exit codes: 0 on success, including when nothing matched; 2 for an invalid duration or missing `--older-than`; 1 if any deletion failed. A failure on one bundle does not stop the others.

## Acceptance criteria

- **AC1.** With bundles aged 1, 5, and 10 days (all uploaded), `--older-than 7d` deletes only the 10-day bundle and its marker.
- **AC2.** A pending 10-day bundle is kept without `--include-pending` and deleted with it.
- **AC3.** `--dry-run --json` lists the 10-day bundle in `deleted`, sets `dry_run: true`, and the file still exists.
- **AC4.** `--older-than 7x` exits 2 with an error on stderr.
- **AC5.** If one bundle cannot be deleted (permission error), the others are still deleted, it appears in `failed`, and the exit code is 1.

## Non-functional constraints

- Only files in the configured bundle directory that match the bundle naming scheme are ever deleted. Symlinks are never followed or deleted.
- No new dependencies.
- Works on macOS and Linux.

## Out of scope

- Deleting bundles from the remote bucket.
- A config-file default for `--older-than`.
- Scheduling (cron or launchd setup).
