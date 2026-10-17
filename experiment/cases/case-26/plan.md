# Plan: Cursor pagination for `GET /v1/invoices`

## Overview

Replace offset pagination in the invoices route and repository with keyset pagination on `created_at`, add a `created_after` filter, and add a supporting index for the filtered queries. Cursors are small base64 JSON blobs carrying the last row's `created_at` and `id`. The response keeps the `{ data, next_cursor }` shape already used by `/v1/customers`.

## Steps

1. **Index.** Add `migrations/004_invoices_status_idx.sql` with `CREATE INDEX CONCURRENTLY invoices_tenant_status_idx ON invoices (tenant_id, status)`. Status-filtered listings are the slow ones in the current dashboards, and this index lets Postgres jump straight to the tenant's paid or open invoices, which keeps AC6 within budget.

2. **Repository.** Change `listInvoices` in `src/repos/invoiceRepo.ts` to take `{ after: { createdAt } | null, limit, status?, createdAfter? }`. The query is `WHERE tenant_id = $1 [AND status = ..] [AND created_at > ..] [AND created_at < $after] ORDER BY created_at DESC LIMIT limit + 1`, and the extra row decides whether there is a next page. `created_after` is passed as a bound parameter, never interpolated, and the returned columns stay identical to today's so existing clients parsing `data` are unaffected.

3. **Cursor helpers.** Add `encodeInvoiceCursor(row)` and `decodeInvoiceCursor(raw)` at the top of `src/routes/invoices.ts`, using `Buffer.from(JSON.stringify({ c: created_at, i: id })).toString("base64url")`. These cursors carry only a timestamp and an id from the caller's own result set, so they don't need the HMAC used for customers.

4. **Malformed cursors.** If `decodeInvoiceCursor` fails to parse, treat the request as having no cursor and return the first page. This matches how `/v1/customers` treats an unreadable cursor and avoids breaking integrations that cache stale cursors.

5. **Route parameters.** In the invoices route, keep `parseLimit(req.query.limit, { def: 25, max: 100 })` and the existing status validation. Parse `created_after` with `Date.parse` and throw `ValidationError("invalid_created_after")` on `NaN`.

6. **Offset removal.** Remove the `offset` parameter and its validation from the route and repository. Requests that still send `offset` get the first page with a cursor, so integrations migrate naturally the next time they run.

7. **Response.** Return `{ data: rows, next_cursor }`, where `next_cursor` is `encodeInvoiceCursor(lastRow)` when the extra row was present, and `null` otherwise.

8. **Docs.** Update the public API reference for `GET /v1/invoices` with the new parameters, an example two-page walk, and a short migration note for `offset` users.

9. **Changelog.** Add an entry to the developer changelog announcing cursor pagination and the `created_after` filter.

## Test strategy

Extend `test/invoices.test.ts` (supertest with the existing fake `db`):

- First page returns 25 rows and a `next_cursor`; following it returns the next rows (AC1 scenario with distinct timestamps).
- `limit=101` still returns `invalid_limit`.
- Unknown `status` still returns `invalid_status`; invalid `created_after` returns `invalid_created_after`.
- A garbage cursor returns the first page.
- `next_cursor` is `null` on the last page.

Performance (AC6) will be checked with `EXPLAIN ANALYZE` on the staging copy of the largest tenant after the index from step 1 is built.

## Rollout

- Build the index concurrently ahead of the code deploy so there is no lock on `invoices`.
- Deploy behind the usual canary (5% for one hour), watching p95 and the 4xx rate on `/v1/invoices`.
- Email integrators who used `offset` in the last 30 days, linking the migration note.
- Roll back by redeploying the previous build; the index can stay, since nothing else depends on it.
