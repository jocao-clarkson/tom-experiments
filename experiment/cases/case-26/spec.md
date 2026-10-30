# Spec: Cursor pagination for `GET /v1/invoices`

## Goal

Large tenants page through `GET /v1/invoices` with `offset`, which gets slower the deeper they go and returns duplicate or missing rows when invoices are created mid-export. Move the endpoint to cursor pagination, as `/v1/customers` already does, and add a date filter that integrators have asked for.

## Functional requirements

- **R1.** `GET /v1/invoices` accepts `cursor` and `limit` (default 25, max 100; out of range returns 400 `invalid_limit`).
- **R2.** Results are ordered by `created_at` descending, then `id` descending. Paging must neither repeat nor skip an invoice, including when many invoices share a `created_at` (bulk imports write thousands with the same timestamp) and when new invoices are created between page requests.
- **R3.** Optional filters `status` (`draft|open|paid|void`) and `created_after` (ISO 8601). A cursor is only valid with the filters it was issued for.
- **R4.** Response shape: `{"data": [...], "next_cursor": string | null}`. Items in `data` keep today's invoice representation, field for field and format for format (for example `"created_at": "2024-05-01T09:30:00.000Z"`).
- **R5.** A malformed, tampered, or mismatched cursor (wrong tenant or filters) returns 400 `invalid_cursor`.
- **R6.** For a 90-day deprecation window, `offset` keeps working as today. Responses to `offset` requests carry `Deprecation: true` and a `Link` header pointing to the migration guide. Sending both `offset` and `cursor` returns 400 `invalid_pagination`.

## Acceptance criteria

- **AC1.** With 60 invoices sharing one `created_at` and `limit=25`, three pages return all 60 exactly once.
- **AC2.** A cursor issued to tenant A, presented by tenant B, returns 400 `invalid_cursor`.
- **AC3.** A cursor issued for `status=paid` and reused with `status=open` returns 400 `invalid_cursor`.
- **AC4.** A garbage `cursor=abc` returns 400 `invalid_cursor`.
- **AC5.** `?offset=50` still works and includes the `Deprecation` header.
- **AC6.** p95 under 150 ms for the first and the 200th page of a tenant with 2 million invoices, with or without `status`.

## Non-functional constraints

- The database is in a change freeze until the Q3 platform upgrade: no migrations (DDL) may ship in this release.
- Cursors must be opaque and unforgeable, consistent with `/v1/customers`.
- No changes to other list endpoints' behaviour.

## Out of scope

- Total counts or page numbers.
- Changing `/v1/customers`.
- Removing `offset` (a later release, after the deprecation window).
- Changes to CI workflows under `.github/workflows/`; the platform team owns them until the Q3 upgrade.
