# Spec: Item reorder endpoint

## Goal

Store managers place supplier reorders by email today, which is slow and leaves no record in the inventory service. Add an API endpoint that places a purchase order with the supplier for a single item and records it, so the dashboard can offer a "Reorder" button.

## Functional requirements

- **R1.** Add `POST /items/{sku}/reorder` with body `{"quantity": <int>}`. Quantity must be an integer from 1 to 500 inclusive. Validate the body with the service's existing request validation; unknown fields are rejected.
- **R2.** An unknown SKU returns 404 `not_found`.
- **R3.** The endpoint creates a purchase order by calling the supplier's `POST /purchase-orders` with `{"sku", "quantity"}`. The supplier API does not support idempotency keys: every POST it receives creates a new purchase order that we are billed for. Each reorder request must create at most one purchase order.
- **R4.** On success, record the reorder in a new `reorders` table (`id`, `sku`, `quantity`, `supplier_po_id`, `status = "pending"`, `created_at`) and return 202 with `{"reorder_id", "supplier_po_id", "status"}`.
- **R5.** If the item already has a reorder with status `pending`, return 409 `conflict` without calling the supplier.
- **R6.** If the supplier call fails or times out, return 502 `upstream_error` and do not record a reorder.

## Acceptance criteria

- **AC1.** Quantity 0, 501, or a non-integer returns 400 `validation_failed`.
- **AC2.** A valid request returns 202, makes one supplier call, and writes one `reorders` row.
- **AC3.** A supplier timeout returns 502, writes no `reorders` row, and the supplier was called exactly once.
- **AC4.** A second reorder while one is pending returns 409 and makes no supplier call.
- **AC5.** Two concurrent reorder requests for the same SKU result in at most one purchase order.

## Non-functional constraints

- Supplier calls follow the existing supplier client conventions (auth header, timeout, logging).
- CI has no network access. Tests must not call the supplier.
- No new third-party dependencies (runtime or dev) in this release; the security review for new packages is backlogged.
- p95 latency under 2 seconds excluding supplier time.

## Out of scope

- Receiving deliveries or marking reorders complete.
- Automatic reorders when stock drops below `reorder_point`.
- Cancelling purchase orders with the supplier.
- Dashboard UI changes.
