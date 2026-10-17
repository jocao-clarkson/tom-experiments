# Plan: `logship collect`

## Overview

`collect` is a new command registered in `internal/cli` like `upload`. File discovery, scrubbing and size selection live in a new `internal/collect` package so the command file stays thin. The bundle is written with the existing streaming `bundle.Writer`, and `--upload` hands the finished file to the existing `uploadBundle` helper.

## Steps

1. **Command registration.** `internal/cli/collect.go` registers `collect` in `init()` with its own `flag.FlagSet`: `--since` (duration, default 24h), `--include-system`, `--upload`, `--ticket`, `--dry-run`, and `--json` for a machine-readable summary. `--upload` without `--ticket` is a usage error (exit 2).

2. **Discovery.** `internal/collect/discover.go`: `Discover(dirs []string, since time.Duration, includeSystem bool)` walks each `log_dirs` entry with `filepath.WalkDir`, keeps regular files with `ModTime` within the window, and, when `includeSystem` is set, appends `/var/log/syslog` or `/var/log/system.log` depending on `runtime.GOOS` if the file exists. It returns candidates sorted newest first, each with path, size and mod time.

3. **Scrubbing.** `internal/collect/scrub.go`: a `Scrub([]byte) ([]byte, int)` function applying two regexes, one for email addresses and one for `Bearer` tokens, which are the two leak types support sees most often in customer logs. Keeping it local to `collect` lets us tune it for bulk file content without affecting the single-line redaction used elsewhere.

4. **Reading files.** For each candidate, `os.ReadFile` the content and pass it to `Scrub`, keeping the scrubbed bytes and the hit count. This gives us the exact redacted size of each file for the cap calculation in step 5. Files that fail to open or read are recorded as skipped with the error text.

5. **Size cap.** Sum the scrubbed sizes newest first, and once adding a file would exceed `cfg.MaxBundleMB`, mark it and all older files as dropped, printing a warning to stderr listing them.

6. **Bundle writing.** Create `logship-<hostname>-<UTC timestamp>.tar.gz` in the working directory, write each kept file via `bundle.Writer.AddFile` using a `bytes.Reader` over the scrubbed content, and close the writer. On any write error, remove the partial bundle.

7. **Dry run.** With `--dry-run`, print the candidate list from step 2 with sizes and stop before step 4.

8. **Upload.** With `--upload`, call `uploadBundle(env, bundlePath, ticket)` from `upload.go`, which already maps upload failure to exit 4.

9. **Summary and exit code.** Print the summary (included, skipped, dropped, redaction count, bundle path) as text, or as one JSON object when `--json` is passed. Exit 0 on success; if any file was skipped, exit 1 so scripts notice something went wrong.

## Test strategy

- `internal/collect/discover_test.go`: builds a temp directory tree with files whose mod times are set via `os.Chtimes`, and checks the `--since` window and newest-first ordering.
- `internal/collect/scrub_test.go`: emails and bearer tokens are masked and counted.
- `internal/cli/collect_test.go`: runs the command against a temp `log_dirs` config, opens the resulting tar.gz and asserts the content is scrubbed (AC1) and that the cap drops the oldest file when `max_bundle_mb` is set to 1 (AC2); `--dry-run` writes no file (R7).
- `test/e2e/collect_system_test.go`: builds the binary and runs `logship collect --include-system --since 1h` on the CI runner, asserting the bundle contains the runner's system log. This is the only check of the system log path handling.

## Rollout and notes

- Released in logship 1.6 via the existing goreleaser pipeline; Homebrew and the apt repo pick it up automatically.
- Support's runbook will change from "send us your logs" to "run `logship collect --upload --ticket <id>`".
- On Linux, `/var/log/syslog` is often readable only by the `adm` group. Operators who are not in that group will see the file listed as skipped, which support can explain.
