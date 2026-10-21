# Plan: Cursor pagination for `GET /v1/invoices`

## Overview

Replace offset pagination in the invoices route and repository with keyset pagination on `(created_at, id)`, add the `created_after` filter, and add an automated performance check for AC6. Cursors are small base64url JSON blobs carrying the last row's `created_at`, `id` and tenant. The response uses the `{ data, next_cursor }` shape already returned by `/v1/customers`.

## Steps

1. **Repository query.** Change `listInvoices` in `src/repos/invoiceRepo.ts` to take `{ after: { createdAt, id } | null, limit, status?, createdAfter? }` and return `{ rows, last }`. The query is `WHERE tenant_id = $1 [AND status = ..] [AND created_at > ..] [AND (created_at, id) < ($c, $i)] ORDER BY created_at DESC, id DESC LIMIT limit + 1`, and the extra row decides whether there is a next page. This walks the existing `invoices_tenant_created_idx` from migration 003, so no new index is needed.

2. **Row shape.** In the same query, select `created_at` as `to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS created_at`, so rows match the `Invoice` type's `created_at: string` and every value is ISO 8601 UTC. All other columns stay as they are.

3. **Cursor helpers.** Add `encodeInvoiceCursor(payload)` and `decodeInvoiceCursor(raw)` at the top of `src/routes/invoices.ts`, using `Buffer.from(JSON.stringify({ c, i, t })).toString("base64url")` and the reverse. A plain JSON payload keeps cursors short and lets support staff read one directly when an integrator reports a stuck export.

4. **Cursor handling.** If `decodeInvoiceCursor` cannot parse the value, or its `t` differs from `req.tenantId`, the route serves the request as a first-page request. Integrations that cache cursors between nightly runs then restart cleanly.

5. **Route parameters.** Keep `parseLimit(req.query.limit, { def: 25, max: 100 })` and the existing status validation. Parse `created_after` with `Date.parse` and throw `ValidationError("invalid_created_after")` on `NaN`; pass the normalised ISO string to the repository.

6. **Offset removal.** Remove the `offset` parameter and its validation from the route and repository. Requests that still send `offset` get the first page with a cursor, so integrations move over the next time they run.

7. **Response.** Return `{ data: page.rows, next_cursor }`, where `next_cursor` is `encodeInvoiceCursor({ c: page.last.created_at, i: page.last.id, t: req.tenantId })` when there is a next page, and `null` otherwise. `c` is the row's `created_at` string exactly as the repository returned it.

8. **Performance check.** Add `.github/workflows/invoices-perf.yml` and `scripts/seed-invoices.ts`. The job starts a Postgres 16 service container, applies the migrations, seeds 2 million invoices for one tenant (including a 5,000-row bulk batch sharing one timestamp), then requests page 1 and page 200 with and without `status` fifty times each and fails if p95 exceeds 150 ms. It runs on pull requests that touch `src/repos/invoiceRepo.ts` or `src/routes/invoices.ts`.

9. **Docs.** Update the public API reference for `GET /v1/invoices` with the new parameters, an example two-page walk, and a migration note for `offset` users.

10. **Changelog.** Add a developer changelog entry announcing cursor pagination and the `created_after` filter.

## Test strategy

Extend `test/invoices.test.ts` (supertest with the existing `fakeDb`):

- First page returns 25 rows and a `next_cursor`; following it returns the remaining rows (AC1 walk with distinct timestamps).
- `limit=101` still returns `invalid_limit`.
- Unknown `status` still returns `invalid_status`; an invalid `created_after` returns `invalid_created_after`.
- A garbage cursor returns the first page.
- `next_cursor` is `null` on the last page.

AC6 is covered by the `invoices-perf` workflow from step 8, which must pass before merge.

## Rollout

- Deploy behind the usual canary (5% for one hour), watching p95 and the 4xx rate on `/v1/invoices`.
- Email integrators who used `offset` in the last 30 days, linking the migration note.
- Roll back by redeploying the previous build; there are no schema changes to revert.
