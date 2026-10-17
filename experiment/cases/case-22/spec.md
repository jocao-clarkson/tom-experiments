# Spec: Refunds feed and net daily revenue

## Goal

Finance reports gross revenue from the warehouse, but refunds live in a separate export from the payments provider. Ingest the daily refunds export into the warehouse and publish net revenue per day so the finance dashboard stops relying on a spreadsheet.

## Functional requirements

- **R1.** Add a `refunds` job to `revpipe` that processes every `refunds_*.csv` file in the input directory. Columns: `refund_id, order_id, amount, currency, refunded_at, customer_email, reason`.
- **R2.** Amounts are positive decimal strings and must be converted to minor units exactly, using the same rules as orders (currency exponent, no rounding). Rows with invalid amounts are rejected with reason `invalid_amount`.
- **R3.** Valid refunds are upserted into a new `refunds` table keyed by `refund_id` (`refund_id, order_id, amount_minor, currency, refunded_at, reason`). Customer email is not stored in this table.
- **R4.** Refunds whose `order_id` is not in `orders` are not loaded. They are written to `DEADLETTER_DIR/refunds-<run date>.csv` with the original row and a `deadletter_reason` column, so they can be replayed once the order arrives.
- **R5.** `daily_revenue` gains `refunds_minor` and `net_minor` (gross minus refunds) per (day, currency), where a refund counts on the UTC day of `refunded_at`.
- **R6.** Re-running the job over the same files must leave `refunds` and `daily_revenue` unchanged.

## Acceptance criteria

- **AC1.** `12.345 USD` is dead-lettered as `invalid_amount`; `0.10 USD` and `0.20 USD` refunds on one day give `refunds_minor = 30`.
- **AC2.** A refund for an unknown order appears in the dead-letter file and not in `refunds`.
- **AC3.** Running the job twice on the same input produces identical `daily_revenue` rows.
- **AC4.** A 2,000,000-row refunds file completes in under 10 minutes with peak RSS below 512 MB on the standard batch worker.

## Non-functional constraints

- Files are processed as streams; the worker has 1 GB of memory shared with a sidecar.
- `customer_email` must never be written unmasked outside the warehouse (log lines, files read by other teams). Use the `pii` package.
- No new Go module dependencies.
- The dead-letter directory is readable by the payments support team.

## Out of scope

- Splitting a refund across multiple days or orders.
- Currency conversion; revenue stays per currency.
- Backfilling refunds from before this release.
- Automatic replay of dead-lettered rows.
