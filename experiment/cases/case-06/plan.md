# Plan: List invoices endpoint

## Overview

We add `listInvoices` in `internal/httpapi/invoices.go` and `Invoices.List` in `internal/store/invoices.go`, and register the route in `router.go`. The created-at sorts reuse the existing keyset cursor from `pagination.go`. That cursor only encodes `(created_at, id)`, so amount sorts use offset pagination with an opaque page token. Filter parsing and its error reporting live in the invoices handler.

## Steps

1. **Store query builder** (`internal/store/invoices.go`). Add `ListOptions{Statuses []string; CustomerID string; CreatedAfter, CreatedBefore *time.Time; Sort string; After *After; Offset, Limit int}`. Build the `WHERE` clause with `github.com/Masterminds/squirrel` (Postgres placeholder format), since the combination of optional filters makes hand-concatenated SQL error-prone. Every query starts from `squirrel.Eq{"tenant_id": tenantID}` (R1, AC4).

2. **Created-at sorts** (`internal/store/invoices.go`). For `-created_at` and `created_at`, apply `(created_at, id) < ($a, $b)` or `>` from `After` and order by `created_at, id` in the matching direction, fetching `limit+1` rows the way `Customers.List` does. This uses the existing `(tenant_id, created_at DESC, id DESC)` index.

3. **Amount sorts** (`internal/store/invoices.go`). For `-amount` and `amount`, order by `amount_cents, id` with `OFFSET` and `LIMIT limit+1`.

4. **Page token for amount sorts** (`internal/httpapi/invoices.go`). Encode the offset as base64 JSON `{"o": 150}` and return it in a `next_page` field, next to `data`. Clients pass it back as `?page=`. Using a separate field stops a created-at cursor and an amount page token from being mixed up (AC5).

5. **Parameter parsing** (`internal/httpapi/invoices.go`). Parse `status` by splitting on commas and checking against the four allowed values. Parse `customer_id` as is. Parse `created_after` and `created_before` with `time.Parse(time.RFC3339, ...)`; values that fail to parse are skipped, so that clients sending date-only strings still get results. Validate `sort` against the four values. Reuse `parseLimit` and `decodeCursor`.

6. **Invoice error helper** (`internal/httpapi/invoices.go`). Add `writeInvoiceError(w, field, msg)`, which writes `400` with `{"error": {"code": "bad_request", "field": "<name>", "message": "..."}}`. The shared `writeError` has no slot for the parameter name, and changing it would affect every endpoint.

7. **Handler** (`internal/httpapi/invoices.go`). `listInvoices(s InvoiceLister)` reads the tenant from `auth.TenantID`, calls the store, trims to `limit`, and sets `next_cursor` (created-at sorts) or `next_page` (amount sorts). Each item is a `store.Invoice`, the same struct `Get` returns (R6). Empty results return `"data": []`.

8. **Routing** (`internal/httpapi/router.go`). Add `Invoices InvoiceLister` to `Deps` and register `GET /v1/invoices` on the authenticated `api` mux.

9. **Docs** (`docs/api/invoices.md`). Document the parameters and both pagination tokens for the SDK team.

## Test strategy

- `internal/httpapi/invoices_test.go`, using a fake `InvoiceLister` in the same style as `customers_test.go`:
  - the handler passes the tenant from context to the store;
  - `?status=open,paid&limit=2` returns two items and a `next_cursor` (AC1);
  - `?sort=-amount` returns `next_page` and no `next_cursor`;
  - an unknown status returns 400.
- `internal/store/invoices_test.go`: a table test asserting the generated SQL and arguments for each filter combination, including that `tenant_id` is always the first predicate.
- A handler test that `limit=0` and `limit=201` are rejected through the shared `parseLimit`.
- `go test ./...` in CI as usual.

## Rollout and notes

- The endpoint is additive and goes out behind no flag. The API changelog will announce it once SDK support lands.
- We will check `EXPLAIN ANALYZE` against the largest tenant on the staging snapshot before release.
- Amount sorting is expected to be used mainly for small result sets (filtered by customer or status), so offset pagination is acceptable there.
- `squirrel` is a small, widely used library with no transitive dependencies. We'll mention it in the PR for platform sign-off.
