# Spec: Bulk price updates

**Service:** `catalog` · **Requested by:** Pricing Ops

## Goal

Pricing Ops reprices whole categories at once (seasonal sales, supplier changes). Today their tooling calls `PATCH /v1/products/{sku}/price` hundreds of times, and when one call fails halfway the catalog ends up with half a sale applied. We want a bulk endpoint that applies a set of price changes as a unit.

## Functional requirements

- **R1.** Add `PUT /v1/products/prices` accepting `{ "items": [ { "sku", "price_cents", "currency" } ] }` with 1 to 500 items. More than 500 items, or an empty list, returns `400`.
- **R2.** Each item is validated with the same rules as the single-item endpoint. Unknown SKUs and duplicate SKUs within a request are validation errors too. If **any** item is invalid, respond `422` with `error.details` listing `{ index, sku, message }` for every failing item, and apply **nothing**.
- **R3.** Valid requests are applied in a single database transaction: either all prices change or none do.
- **R4.** For each changed SKU, a `price_changed` outbox event is written in that same transaction, with the same payload shape the single-item endpoint uses.
- **R5.** After a successful commit, the product cache entries for the changed SKUs are invalidated, and the endpoint responds `200` with `{ "updated": n }`.
- **R6.** The endpoint requires the `catalog:write` scope, like the single-item endpoint.

## Acceptance criteria

- **AC1.** A request of 500 valid items updates all 500 prices and writes 500 outbox rows.
- **AC2.** A request with 499 valid items and one unknown SKU returns 422 naming that item, and no price or outbox row changes.
- **AC3.** If the database fails mid-request, no price changes are visible afterwards.
- **AC4.** A caller without `catalog:write` gets 403.
- **AC5.** Errors use the standard `apierr` envelope.

## Non-functional constraints

- A 500-item request must complete in under 2 seconds at p95.
- The checkout service reads prices from the same `products` rows, so row locks must be held as briefly as possible; long lock waits show up as checkout latency.
- No new infrastructure or third-party dependencies.

## Out of scope

- Scheduled (future-dated) price changes.
- Changes to the single-item `PATCH` endpoint's behaviour.
- Bulk updates to fields other than price and currency.
