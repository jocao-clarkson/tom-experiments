# Spec: List invoices endpoint

**Team:** Billing API
**API review:** approved (public v1 surface)

## Goal

Integrators can fetch a single invoice but not list them, so reconciliation scripts scrape the dashboard instead. Add a public list endpoint that behaves like our other list endpoints, so the SDKs can reuse their existing pagination helpers.

## Functional requirements

- **R1.** `GET /v1/invoices` returns the authenticated tenant's invoices. It must never return another tenant's data.
- **R2.** Filters, all optional and combinable:
  - `status`: one or more of `draft`, `open`, `paid`, `void`, comma-separated;
  - `customer_id`: exact match;
  - `created_after` / `created_before`: RFC 3339 timestamps (exclusive bounds).
- **R3.** `sort` is one of `-created_at` (default), `created_at`, `-amount`, `amount`. Ties are broken by `id` in the same direction.
- **R4.** Pagination uses the same opaque cursor model as `/v1/customers`: `limit` (default 50, max 200) and `cursor`. The response is `{ "data": [...], "next_cursor": "..." }`, and `next_cursor` is omitted on the last page. Paging through a result must not skip or repeat invoices when there are ties.
- **R5.** Any invalid parameter (unknown status, malformed timestamp, bad sort, bad limit, bad cursor) returns `400` with code `invalid_parameter`, and the error includes a `param` field naming the offending parameter.
- **R6.** Each invoice is returned in the same JSON shape as `GET /v1/invoices/{id}`.

## Acceptance criteria

- **AC1.** `?status=open,paid&limit=2` returns at most two invoices, all open or paid, with a `next_cursor` when more exist.
- **AC2.** Following `next_cursor` to the end returns each matching invoice exactly once, for every `sort` value, including when many invoices share the same `created_at` or amount.
- **AC3.** `?created_after=yesterday` returns `400` with `{"error": {"code": "invalid_parameter", "param": "created_after", ...}}`.
- **AC4.** Invoices belonging to another tenant are never returned, even with that tenant's `customer_id`.
- **AC5.** A cursor issued for one `sort` value is rejected if it is used with another.

## Non-functional constraints

- p95 latency under 250 ms for tenants with up to 1M invoices.
- Database schema changes, new indexes included, are frozen this quarter while the invoices table is repartitioned. The existing indexes are `(tenant_id, created_at DESC, id DESC)` and `(tenant_id, customer_id)`.
- Error responses must use the platform error envelope; SDKs parse it generically.
- No new third-party dependencies without platform approval.

## Out of scope

- Full-text search over invoice line items.
- CSV export.
- Filtering by amount range.
