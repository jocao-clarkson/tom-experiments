# Plan: `PUT /v1/products/prices`

## Overview

A new `BulkPricesHandler` in `internal/api` validates the whole request up front, applies the price changes in one transaction, then records outbox events and invalidates the cache. Validation reuses `priceRequest.validate()` so single and bulk rules cannot drift.

## Steps

1. **Request types.** In `internal/api/bulk_prices.go`, define `bulkPriceRequest { Items []bulkItem }` where `bulkItem` embeds `priceRequest` plus `SKU`. Decode with `json.Decoder.DisallowUnknownFields`. An empty list or more than 500 items returns `apierr.Write(w, 400, "bad_request", ...)`.

2. **Per-item validation.** Loop over items, call the embedded `validate()`, and track SKUs in a map to catch duplicates. Collect `{index, sku, message}` for every failure; if any exist, respond `422 validation_failed` with the list in `details`, and stop before touching the database.

3. **Store access.** Add a `DB() *sql.DB` accessor on `store.Store` so the bulk handler can manage its own transaction. The single-item path keeps using `Store.UpdatePrice` unchanged.

4. **Apply prices.** In the handler, `BeginTx` on `r.Context()`, then for each item run `UPDATE products SET price_cents = $1, currency = $2, updated_at = now() WHERE sku = $3`. Unknown SKUs are expected occasionally when Pricing Ops' export lags behind catalog deletions, so an item with `RowsAffected() == 0` is skipped and its SKU added to a `skipped` list instead of failing the whole batch. Commit at the end.

5. **Outbox events.** After the price transaction commits, open a second transaction and call `outbox.Enqueue` once per updated SKU with a `price_changed` event keyed by SKU and the payload `sku`, `price_cents`, `currency`. If the outbox transaction fails, log at error level with the SKU list so the relay can be backfilled.

6. **Cache invalidation.** Call `h.Cache.Delete(updatedSKUs...)` once both transactions have finished. `TTL.Delete` already accepts multiple keys.

7. **Response.** Return `200` with `{ "updated": n, "skipped": [...] }`.

8. **Routing.** In `internal/api/router.go`, register `PUT /v1/products/prices` and extend `NewRouter` to take the bulk handler. Requests are already authenticated by the `authenticate` wrapper around the mux, and Pricing Ops' tooling is the only caller with gateway access to this path.

9. **Wiring.** Construct `BulkPricesHandler` with the same `*store.Store` and product cache as `ProductsHandler`, so invalidation hits the cache the `GET` path reads.

10. **Metrics.** Add a histogram `catalog_bulk_price_items` for batch sizes and reuse the existing request-duration histogram labels for the new route.

## Test strategy

- `internal/api/bulk_prices_test.go` (new): table tests for request-shape errors (empty, 501 items, unknown fields), per-item validation errors including duplicate SKUs, and the 422 `details` format. These exercise the handler up to the point where it would open a transaction, so they need no database.
- Extend `products_test.go` to confirm the shared `validate()` still behaves the same for the single-item endpoint.
- `internal/api/bulk_prices_integration_test.go` (new, build tag `integration`): runs a 500-item request against the `CATALOG_TEST_DSN` database used by the store integration tests and asserts 500 updated prices and 500 outbox rows (AC1), plus the p95 timing over 20 runs.

## Rollout and notes

- No migration is required; the `products` and `outbox` tables are unchanged.
- Pricing Ops will switch their tool to the bulk endpoint for the next seasonal sale; the single-item endpoint stays for ad-hoc fixes.
- Expected load is a few dozen bulk requests per day, mostly during business hours, with the largest batches at the start of a sale.
- The API reference will document the 500-item limit, the 422 `details` shape, and the `skipped` list, so Pricing Ops' tool can show which SKUs need attention.
- The handler wraps the body in `http.MaxBytesReader` at 256 KB; 500 items of this shape are well under 100 KB, so oversized bodies fail fast with 400.
- The search indexer and price-history consumers already subscribe to `price_changed`, so bulk updates reach them with no consumer changes.
