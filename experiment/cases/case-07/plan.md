# Plan: Supplier price list import

## Overview

The new job, `prices_import`, has the same shape as `inventory_import`: discover files with `DropFolder`, validate with `Validator`, upsert in a single transaction, write a reject report, then move the file. What's new is the 5% whole-file threshold and a quarantine destination.

## Steps

1. **Quarantine support** (`pipeline/sources.py`). Add an optional `quarantine_dir` to `DropFolder.__init__` and a `quarantine(f)` method that reuses `_move`. `inventory_import` does not pass it, so its behaviour is unchanged.

2. **Job module** (`pipeline/jobs/prices_import.py`, new). `PATTERN = r"prices_(?P<supplier>[a-z0-9]+)_(?P<date>\d{8})\.csv"`. `run(cfg, db)` builds `DropFolder(cfg.drop_dir / "prices", cfg.archive_dir / "prices", quarantine_dir=cfg.drop_dir.parent / "quarantine" / "prices")` and returns a list of `FileOutcome`, reusing the dataclass from `inventory_import`. The dataclass moves to `pipeline/jobs/__init__.py`.

3. **Header check** (`prices_import.py`). After opening the file with `csv.DictReader`, compare `reader.fieldnames` with the four required columns. If any are missing, write a one-line reject report (line 1, reason `missing_columns:<names>`), quarantine the file, and continue to the next file (R2, R6).

4. **Row rules** (`prices_import.py`). Plain functions passed to `Validator(required=[...], rules=[...])`:
   - `unknown_sku`, checked against `db.existing_values("products", "sku")`, loaded once per run;
   - `unit_price` must first match `^\d+(\.\d+)?$`, or it gets `unit_price_invalid` (this rejects `abc`, `NaN`, `1e2` and signs). It is then parsed with `decimal.Decimal`, giving `unit_price_not_positive` for values equal to 0 and `unit_price_precision` for more than two decimal places (AC3);
   - `currency_unsupported` when not in `{"USD", "EUR", "GBP"}`;
   - `effective_date_invalid` when `date.fromisoformat` fails or the value is not exactly 10 characters.

   `Validator` already reports `missing:<cols>` for blank required values and records line numbers starting at 2 (R5).

5. **Threshold** (`prices_import.py`). If `result.reject_ratio > 0.05`, write the reject report, quarantine the file, log at WARNING, and record `loaded=0`. A strict `>` means exactly 5% still loads (AC1). A header-only file has `total == 0` and ratio 0.0, so it falls through to the normal path (AC6).

6. **Row mapping** (`prices_import.py`). Map each valid row to `{"supplier", "sku", "effective_date", "unit_price_cents", "currency"}`, with `unit_price_cents = int(Decimal(v) * 100)`. Step 4 guarantees at most two decimals, so this is exact (R4).

7. **Load** (`prices_import.py`). `with db.transaction(): db.upsert("supplier_prices", rows, key=("supplier", "sku", "effective_date"), chunk_size=cfg.upsert_chunk_size)`. One transaction per file means a failure rolls back the whole file (AC5), and the keyed upsert makes reruns idempotent (AC4).

8. **Report and archive** (`prices_import.py`). After commit, write the reject report (when there are rejects) and archive the file.

9. **Register** (`pipeline/cli.py`). Add `"prices_import": prices_import.run` to `JOBS`, and add a `[jobs.prices_import]` section to the deployed `merch-batch.toml` that inherits the paths from `[defaults]`.

## Test strategy

New `tests/test_prices_import.py`, built on the same `tmp_path` and SQLite fixture pattern as `test_inventory_import.py`, with a `supplier_prices` table created in the fixture:

- AC1 and AC2 as boundary tests with 100-row generated files (5 and 6 bad rows).
- AC3: parametrised rule tests for `12.345`, `0`, `-1`, `abc`, `NaN`, and `1e2`.
- AC4: run twice and compare a full table snapshot.
- AC5: replace `db.conn` with a thin proxy whose `executemany` raises on its second call (with `upsert_chunk_size=2`, so one chunk has already been written), then assert the table is empty and the file is still in `drop/`.
- AC6: header-only file, plus a missing-column file that ends up in quarantine.
- A 200k-row file marked `@pytest.mark.slow`, registered in `pyproject.toml` (the suite uses `--strict-markers`) and deselected by default with `-m "not slow"`. It checks the runtime against the 10-minute budget.

## Rollout and notes

- Run once by hand against last week's files in staging and compare the totals with the buyer's spreadsheet.
- If the process dies after commit but before archive, the file is reprocessed on the next run. The idempotent upsert makes that harmless.
- The reject report reuses the source stem, so a re-sent file overwrites its earlier report.
