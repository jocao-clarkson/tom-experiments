# Plan: `logship prune`

## Overview

`prune` is a new subcommand in `logship/cli.py` backed by a small pure function in a new `logship/prune.py`. It reuses `list_bundles` for discovery and name-based timestamps, `parse_duration` for `--older-than`, and `Output` for human, JSON and quiet modes. The deletion logic takes `now` and the bundle list as inputs so it can be tested without touching the clock.

## Steps

1. **Selection function.** In `logship/prune.py`, add `select_for_prune(bundles, older_than, now, include_pending) -> list[Bundle]`. A bundle is eligible when `now - bundle.created_at > older_than` and (`bundle.uploaded` or `include_pending`). Because `list_bundles` derives `created_at` from the file name, R2 holds without extra work. The cutoff is strict (`>`), so a bundle exactly 7 days old is kept; this is noted in the help text.

2. **Deletion function.** Add `delete_bundles(bundles, bundle_dir, dry_run) -> PruneResult` (dataclass with `deleted`, `failed`, `bytes_freed`). For each bundle, oldest first, as `list_bundles` returns them: skip anything for which `path.is_symlink()` is true or whose `path.resolve().parent` is not `bundle_dir.resolve()`. Otherwise, unless `dry_run`, call `path.unlink()` and then `bundle.marker.unlink(missing_ok=True)`. Any `OSError` adds the name to `failed` and continues with the next bundle. `bytes_freed` sums `bundle.size` for deleted entries.

3. **Symlinks in discovery.** `list_bundles` uses `entry.is_file()`, which follows symlinks, so a symlinked bundle would be listed. Rather than change `list_bundles` (used by `list`), the symlink check in step 2 is the guard, and a skipped symlink is reported via `out.info`, not counted as failed.

4. **Argument parsing.** In `build_parser()`, add a `prune` subparser with `--older-than` (required), `--include-pending`, and `--dry-run`. `--older-than` is parsed as a plain string; validation happens in the command so the error goes through `Output.error` and returns `EXIT_USAGE`. A missing `--older-than` is rejected by argparse itself, which also exits 2.

5. **Command handler.** Add `cmd_prune(args, cfg, out)` in `cli.py`: call `parse_duration`, catching `ValueError` and returning `EXIT_USAGE` after `out.error(str(exc))`. Then call `list_bundles(cfg.bundle_dir)`, `select_for_prune(...)` with `datetime.now(timezone.utc)`, and `delete_bundles(...)`.

6. **Output.** For each deleted name, `out.info(f"deleted {name}")`, or `would delete` in dry-run mode. Finish with `out.result({...}, summary)` where the summary uses the existing `_human_size`, for example `pruned 3 bundle(s), freed 41.2 MB`. Failures each call `out.error(f"could not delete {name}: {exc}")`, so they still reach stderr under `--quiet`.

7. **Exit code.** Return `EXIT_FAILURE` if `result.failed` is non-empty, else `EXIT_OK`.

8. **Help and README.** Add a `help=` string for the subcommand and each flag, and a short "Pruning old bundles" section to the README with a cron example the user can adapt.

## Test strategy

New `tests/test_prune.py`, reusing the `bundle_dir` fixture and `make_bundle` helper pattern from `tests/test_cli.py` (moved into `tests/conftest.py` so both files share them):

- Unit tests of `select_for_prune` with a fixed `now`: AC1 ages, the exact-boundary case, and pending handling for AC2.
- `delete_bundles` against `tmp_path`: marker removal (R4), dry-run leaves files (AC3), and a symlink pointing outside the directory is untouched.
- CLI-level tests through `cli.main([...])` with `capsys`: `--json --dry-run` output shape (AC3), `--older-than 7x` exits 2 with stderr text (AC4).
- AC5: monkeypatch `Path.unlink` to raise `PermissionError` for one specific name; assert the other bundle is gone, `failed` lists the first, and exit code 1. This avoids relying on `chmod` behaviour, which differs when tests run as root in CI.

Ages in CLI-level tests are set relative to the real clock with a margin of hours, so they don't flake around midnight.

## Rollout

- Release as 0.10.0 with a changelog entry; no config changes.
- `prune` is opt-in, so existing installs are unaffected until someone runs it.
