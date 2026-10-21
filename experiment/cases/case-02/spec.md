# Spec: Purchases stream ingestion

**Team:** Data Platform, ingest squad
**Reviewers:** Analytics Engineering, Commerce

## Goal

Commerce now publishes purchase events from all storefronts (priced in USD, EUR, GBP, JPY and KWD) to the `purchases.v2` topic. Analytics needs them in the warehouse `purchases` table, alongside clicks, within a couple of minutes, so that the conversion dashboards stop depending on the nightly export.

## Functional requirements

- **R1.** Consume the `purchases.v2` topic as a new ingest stream named `PURCHASES`, configured the same way as existing streams.
- **R2.** Transform each event into a `purchases` row with `event_id`, `order_id`, `user_id`, `amount_cents` (integer, converted from the decimal string `amount`), `currency` (upper-cased ISO 4217 code), `revision`, and `occurred_at` in UTC.
- **R3.** Events that are missing `event_id`, have an unparseable `amount`, or have a currency that is not three letters go to `purchases_dlq` with reason codes `missing_event_id`, `invalid_amount` or `invalid_currency`.
- **R4.** Rows are written in batches of the stream's configured batch size.
- **R5.** Source offsets are committed only after the batch's rows (including DLQ rows) have been durably written.
- **R6.** Commerce re-emits a corrected purchase with the same `event_id` and a higher `revision`. The `purchases` table must hold exactly one row per `event_id`, containing the highest revision received. Redelivered messages must not create duplicates or roll a row back to an older revision.
- **R7.** Emit the `rows_ingested` and `rows_dead_lettered` counters for the stream, with dead-lettered rows broken down by reason code so on-call can tell bad amounts from bad currencies.

## Acceptance criteria

- **AC1.** Replaying the same batch twice leaves the `purchases` table unchanged after the second run.
- **AC2.** Delivering revision 2 then revision 1 of an event leaves revision 2 in the table.
- **AC3.** An event with `amount: "12.3x"` lands in `purchases_dlq` with reason `invalid_amount`, and its offset is committed.
- **AC4.** If the warehouse is unavailable, no offsets are committed and no rows are lost once the warehouse recovers.
- **AC5.** A USD event with `amount: "19.99"` becomes `amount_cents` `1999`, and currency `"usd"` becomes `USD`.

## Non-functional constraints

- End-to-end lag under 2 minutes at a sustained 5,000 events/s.
- Write retries follow the platform retry policy (bounded attempts, backoff, configurable per stream).
- No new external services.
- The `purchases` and `purchases_dlq` tables are created by the warehouse migrations repo and already exist with a unique key on `event_id`.

## Out of scope

- Backfilling historical purchases from the nightly export.
- Currency conversion.
- Changes to the warehouse table schemas.
