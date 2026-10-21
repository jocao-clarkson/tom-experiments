# Plan: `logship collect`

## Overview

`collect` is a new command registered in `internal/cli` like `upload` and `doctor`. File discovery, scrubbing and size selection live in a new `internal/collect` package. The bundle is written with the existing streaming `bundle.Writer`, and the summary goes through `env.Out` so the global `--output` flag applies.

## Steps

1. **Command registration.** `internal/cli/collect.go` registers `collect` in `init()` with its own `flag.FlagSet`: `--since` (duration, default 24h), `--include-system`, `--upload`, `--ticket` and `--dry-run`. `--upload` without `--ticket` is a usage error (exit 2).

2. **Discovery.** `internal/collect/discover.go`: `Discover(dirs []string, since time.Duration, includeSystem bool)` walks each `log_dirs` entry with `filepath.WalkDir` and keeps regular files whose `ModTime` is within the window. When `includeSystem` is set it appends `/var/log/syslog` on Linux or `/var/log/system.log` on macOS, chosen by `runtime.GOOS`, if the file exists. It returns candidates sorted newest first, each with path, size and mod time from `os.Stat`.

3. **Scrubbing.** `internal/collect/scrub.go`: `Scrub([]byte) ([]byte, int)` applies two regexes, one for email addresses and one for `Bearer` tokens, which are the two leak types support sees most often in customer logs. Keeping it local lets us tune it for bulk content without affecting the redaction used elsewhere.

4. **Size cap.** `internal/collect/select.go`: `Select(cands, maxBytes)` sums candidate sizes newest first, and once adding a file would exceed `cfg.MaxBundleMB`, marks it and all older files as dropped. Selection happens before any file is opened, so dropped files are never read. `collect.go` prints a warning to stderr naming the dropped files.

5. **Reading files.** For each kept file, `os.ReadFile` the content and pass it to `Scrub`, keeping the scrubbed bytes and the hit count. Files that fail to open or read are recorded as skipped with the error text.

6. **Bundle writing.** Create `logship-<hostname>-<UTC timestamp>.tar.gz` in the working directory, write each scrubbed file via `bundle.Writer.AddFile` with `int64(len(scrubbed))` and a `bytes.Reader`, and close the writer. On any write error, remove the partial bundle.

7. **Dry run.** With `--dry-run`, print the kept list from step 4 with sizes and stop before step 5.

8. **Upload.** With `--upload`, open the finished bundle and call `transport.New(env.Cfg.Endpoint, env.Cfg.Token).Upload` with a 30-minute context, since collected bundles can reach `max_bundle_mb` and are usually larger than hand-picked files. On success, print `uploaded <bundle> to ticket <id>` to stderr; on failure, print the error and set the exit code to 4.

9. **Summary.** Build a `collectResult` struct with `included`, `skipped` (path and reason), `dropped`, `redactions` and `bundle` fields, and render it with `env.Out.Result(res, text)`.

10. **Exit code.** Exit 0 on success; if any file was skipped, exit 1 so scripts notice something went wrong; an upload failure from step 8 takes precedence with exit 4.

## Test strategy

- `internal/collect/discover_test.go`: uses `os.Chtimes` on temp files to check the `--since` window and newest-first ordering.
- `internal/collect/select_test.go`: table tests for the cap, including exactly-at-cap and a single file larger than the cap.
- `internal/collect/scrub_test.go`: emails and bearer tokens are masked and counted.
- `internal/cli/collect_test.go`: runs `cli.Run` with `--config` pointing at a temp file whose `log_dirs` is a temp directory, opens the resulting tar.gz and asserts the content is scrubbed (AC1), that the oldest file is dropped when `max_bundle_mb` is 1 (AC2), that `--dry-run` writes no file (R7), and that `--output json` decodes into the summary struct (AC5).
- `test/e2e/collect_system_test.go`: builds the binary and runs `logship collect --include-system --since 1h` on the CI runner, asserting the bundle contains the runner's system log. This is the only check of the system log path handling.

## Rollout and notes

- Released in logship 1.6 via the existing goreleaser pipeline.
- Support's runbook changes from "send us your logs" to "run `logship collect --upload --ticket <id>`".
- On Linux, `/var/log/syslog` is often readable only by the `adm` group. Operators who are not in that group will see the file listed as skipped, which support can explain.
