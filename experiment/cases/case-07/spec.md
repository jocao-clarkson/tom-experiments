# Spec: Supplier price list import

**Team:** Merchandising Data
**Stakeholders:** Buying, Finance

## Goal

Suppliers send weekly price lists as CSV over SFTP, and a buyer currently pastes them into a spreadsheet. We want a nightly batch job that loads them into `supplier_prices`, so that margin reports use current costs, and that refuses files that are clearly broken instead of half-loading them.

## Functional requirements

- **R1.** The job processes files in `drop/prices/` named `prices_<supplier>_<YYYYMMDD>.csv`, where `<supplier>` is lowercase alphanumeric. Other files are ignored.
- **R2.** Files have a header row with the columns `sku`, `unit_price`, `currency`, `effective_date`. A file missing any of these columns is rejected as a whole (see R6).
- **R3.** A row is valid when:
  - `sku` exists in `products`;
  - `unit_price` is a decimal greater than 0 with at most two decimal places;
  - `currency` is one of `USD`, `EUR`, `GBP`;
  - `effective_date` is a valid `YYYY-MM-DD` date.
- **R4.** Valid rows are upserted into `supplier_prices` keyed by `(supplier, sku, effective_date)`, with the price stored as integer `unit_price_cents`.
- **R5.** Invalid rows are listed in a reject report with the source line number and a reason code.
- **R6.** If **more than 5%** of a file's data rows are invalid, or the header is incomplete, nothing from that file is loaded. The file moves to `quarantine/prices/` and the reject report is still written.
- **R7.** Successfully processed files move to `archive/prices/`. Processing the same file again leaves `supplier_prices` in the same state.

## Acceptance criteria

- **AC1.** A 100-row file with 5 invalid rows loads 95 rows and is archived.
- **AC2.** A 100-row file with 6 invalid rows loads nothing, is quarantined, and has a reject report.
- **AC3.** `unit_price` values `12.345`, `0`, and `abc` are rejected with distinct reason codes.
- **AC4.** Running the job twice on the same file produces no duplicate rows and no changed values.
- **AC5.** If the load fails part-way through a file (for example a database error), no rows from that file remain in `supplier_prices`.
- **AC6.** A header-only file is archived with zero rows loaded.

## Non-functional constraints

- Files can contain up to 200,000 rows. The nightly job must finish one such file in under 10 minutes.
- Use the existing job structure (`DropFolder`, `Validator`, `Database.upsert`, reject reports). No new dependencies.
- Monetary values must not pass through binary floating point.
- `supplier_prices` already exists (created by the DBA migration MD-88) with a unique key on `(supplier, sku, effective_date)`.

## Out of scope

- Currency conversion.
- Notifying suppliers about rejected rows.
- Historical backfill of price lists received before launch.
