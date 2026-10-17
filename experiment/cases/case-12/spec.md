# Spec: USD normalisation for order events

**Team:** Data Platform · **Reviewers:** Finance Analytics

## Goal

Revenue dashboards sum `amount` across currencies, which overstates revenue in weak currencies. We will add an `amount_usd` column to `analytics.events_clean`, computed during the nightly events pipeline from the daily FX table that Treasury already maintains (`ref.fx_rates_daily(rate_date, currency, usd_rate)`), and backfill the last 90 days.

## Functional requirements

- **R1.** For every clean event with a non-null `amount`, set `amount_usd = amount * usd_rate` using the rate for the event's `occurred_at` date (UTC) and its `currency`. Round half-even to 2 decimal places. Events with no amount get `amount_usd = NULL`.
- **R2.** If no rate exists for that date and currency, the event must not be loaded with a guessed value. It goes to `analytics.events_quarantine` with `reason = "missing_fx_rate"`, like other quarantined rows.
- **R3.** Add a `backfill` subcommand: `events-pipeline backfill --days N` (default 90, max 120) reprocesses the last N day partitions, **most recent first**, so current-quarter dashboards recover first.
- **R4.** Re-running the nightly job or the backfill for a partition must leave exactly one copy of each event in the clean and quarantine tables.
- **R5.** Rates for a partition are fetched with a single query, not one query per event.
- **R6.** Each processed partition logs a summary with `loaded`, `quarantined`, and a per-reason breakdown of quarantined counts.

## Acceptance criteria

- **AC1.** An EUR event on a date with a rate gets the correctly rounded `amount_usd`.
- **AC2.** An event whose currency has no rate for that day appears in quarantine with `missing_fx_rate` and not in the clean table.
- **AC3.** Running the backfill twice over the same days yields identical row counts in both tables.
- **AC4.** The partition summary shows the `missing_fx_rate` count.

## Non-functional constraints

- The nightly run starts at 02:00 UTC and must finish by 04:00. A backfill may be running at the same time and must neither block the nightly run nor change where the nightly run resumes from.
- Backfill must be safe to stop with Ctrl-C and restart.
- CI has no warehouse access and no credentials; the test job must finish within 5 minutes.
- No new Python dependencies.

## Out of scope

- Ingesting or correcting FX rates (owned by Treasury).
- Partitions older than 120 days.
- Changes to dashboard SQL.
