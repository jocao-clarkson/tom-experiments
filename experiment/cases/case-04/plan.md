# Plan: `kit export`

## Overview

`export` is a new `cli.Command` in `internal/commands`, built from the same pieces as `list`: `store.List` for data, `cli.CheckFormat` for validation, `cli.WriteJSON` for JSON, and `fsutil.WriteFileAtomic` for the file write. The only new rendering code is a CSV writer on top of `encoding/csv`. The export is rendered into memory, then written in one go. Stores are small, and buffering lets the stdout and file paths share one code path.

## Steps

1. **CSV format constant and writer** (`internal/cli/output.go`). Add `FormatCSV = "csv"` and `WriteCSV(w io.Writer, t Table) error`, which writes `t.Header` then `t.Rows` through `csv.NewWriter`, then calls `Flush` and returns `Error()`. `encoding/csv` already does RFC 4180 quoting (R5, AC4). It takes the existing `Table` type.

2. **Command skeleton** (`internal/commands/export.go`, new). `Export() cli.Command` with flags `--format` (default `json`), `--tag`, `--output`, and `--force`. Positional arguments return `cli.Usagef("export takes no arguments")`, matching `list`.

3. **Validate before doing any work** (`export.go`). Call `cli.CheckFormat(format, cli.FormatJSON, cli.FormatCSV)` first, so an unknown format returns a `UsageError` (exit 2) before the store is read or any file is touched (R6, AC5).

4. **Load projects** (`export.go`). Resolve the path with `store.DefaultPath(io.Getenv)` and call `store.Open(path).List(tag)`. This gives the same tag matching and id ordering as `list` (R1, R2). A nil result is normalised to an empty slice so that JSON renders `[]` (AC6), mirroring `list`.

5. **Render into a buffer** (`export.go`). For JSON, `cli.WriteJSON(&buf, projects)`, which is byte-for-byte what `list --format json` produces (AC2). For CSV, build a `cli.Table` with header `id,name,owner,tags` and rows using `strings.Join(p.Tags, ";")`, then `cli.WriteCSV(&buf, t)`. An empty store gives the header only (AC6).

6. **Stdout path** (`export.go`). With no `--output`, copy the buffer to `io.Out` and return.

7. **Overwrite guard** (`export.go`). With `--output` and no `--force`, `os.Stat` the path; if it exists, return `fmt.Errorf("%s already exists (use --force to overwrite)", path)`, which `cli.App` maps to exit 1 (R4, AC3). Any stat error other than `ErrNotExist` is returned as is.

8. **Atomic write** (`export.go`). `fsutil.WriteFileAtomic(path, buf.Bytes(), 0o644)`. A failure leaves no partial file, and an existing target is untouched until the rename (R7). `os.Rename` replaces an existing file on all three platforms, which is what `--force` relies on.

9. **Register** (`cmd/kit/main.go`). Add `commands.Export()` to the command list.

## Test strategy

All tests go in `internal/commands/export_test.go` and reuse the `golden` helper and the `testdata/projects.json` store from `list_test.go`. The `run` helper is changed to register `Export()` alongside `List()`; the existing list tests are otherwise untouched.

- Golden files `export_csv_infra.golden` (AC1) and `export_csv_all.golden`, which includes the `notes, drafts` row to pin the quoting (AC4).
- AC2: export to `t.TempDir()/out.json` and assert the bytes equal the `list --format json` output from the same run helper.
- AC3: write a sentinel file, run without `--force`, and assert exit 1, `already exists` in stderr, and the file unchanged. Then run with `--force` and assert the new content.
- AC5: `--format xml --output <tmp>/x` exits 2 and the file does not exist.
- AC6: empty `KIT_HOME` for both formats.
- R7: `--output` inside a missing directory returns exit 1 and creates nothing.
- A unit test for `WriteCSV` in `internal/cli/output_test.go` covering quotes and embedded newlines.

## Rollout and notes

- Ships in the next minor release; changelog entry under "Added".
- The existence check and the rename are not one atomic operation. If another process creates the file in between, it will be replaced. For a single-user CLI writing to a user-chosen path, we accept that rather than adding platform-specific exclusive-create logic, and we will note it in the command help for `--force`.
- CI already runs `go test ./...` on Linux, macOS and Windows runners, so the rename behaviour is covered on each platform.
