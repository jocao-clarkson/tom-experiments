# Plan: Item reorder endpoint

## Overview

We add a `reorders` table to the existing SQLite schema, a `reorder` method on `InventoryService`, and a `POST /items/<sku>/reorder` route. Purchase orders are placed through a small dedicated module so the reorder path can tune its own timeout and retry behaviour without affecting the catalog and price lookups. Errors are raised as the existing `APIError` subclasses so the response shape stays consistent with the rest of the API.

## Steps

1. **Schema.** In `inventory/repository.py`, extend `init_schema()` with a `reorders` table (`id INTEGER PRIMARY KEY`, `sku`, `quantity`, `supplier_po_id`, `status`, `created_at`). Add `create_reorder(sku, quantity, po_id)` returning the new row and `get_pending_reorder(sku)` returning the pending row or `None`. Use `StockRepository.now()` for timestamps.

2. **Request schema.** In `inventory/routes.py`, add `REORDER_SCHEMA = {"quantity": {"type": int, "required": True, "min": 1, "max": 1000}}` next to `ADJUST_SCHEMA`, validated through `validate_payload` so unknown fields are rejected the same way as `/adjust`.

3. **Purchase-order module.** Create `inventory/purchase_orders.py` with `place_purchase_order(sku, quantity) -> str`. It reads `SUPPLIER_URL` and `SUPPLIER_API_KEY`, sends `requests.post(f"{url}/purchase-orders", json=..., headers={"Authorization": ...}, timeout=10)`, and returns the `id` from the response body. Wrap the call in a short retry loop (3 attempts, 1s then 2s backoff) on `ConnectionError`, `Timeout` and 5xx, so transient supplier hiccups don't surface to store managers as errors.

4. **Service method.** Add `InventoryService.reorder(sku, quantity)` in `inventory/service.py`: call `get_item(sku)` for the 404 case, call `repo.get_pending_reorder(sku)` and raise `Conflict` if a row exists, call `place_purchase_order`, then `repo.create_reorder(...)`. Return a dict with `reorder_id`, `supplier_po_id` and `status`.

5. **Error mapping.** In `place_purchase_order`, raise `UpstreamError` when the retries are exhausted or the supplier returns a 4xx, including the supplier status in `details`. Because the row is only written after the supplier call returns, a failure leaves no `reorders` row.

6. **Route.** Add `@bp.post("/items/<sku>/reorder")` in `inventory/routes.py` that validates the body, calls `_service().reorder(...)`, and returns `jsonify(result), 202`.

7. **Logging.** Log each placed order at INFO from the service with `sku`, `quantity` and `supplier_po_id`, using the module logger pattern from `supplier_client.py`.

8. **Test dependency.** Add `responses` to the `dev` extra in `pyproject.toml` so tests can intercept the `requests.post` call in `purchase_orders.py` without network access.

9. **Tests.** Add `tests/test_reorder.py` (details below) and keep `tests/test_routes.py` unchanged.

10. **Docs.** Add the endpoint, body, and error codes to the API section of the service runbook so the dashboard team can integrate.

## Test strategy

All new tests live in `tests/test_reorder.py` and use the existing `client` fixture with `responses` registered for `https://supplier.test/purchase-orders`:

- Validation: quantity `0`, a string, and an unknown field each return 400 (AC1).
- Happy path: one registered 200 response, assert 202, the body fields, and one row in `reorders` (AC2).
- Pending conflict: insert a pending row directly, assert 409 and that `responses.calls` is empty (AC4).
- Unknown SKU returns 404.

Supplier failure handling (AC3) is covered by the retry loop in step 3 and will be verified manually against the supplier sandbox before release, since reproducing timeouts reliably in unit tests is awkward. The suite stays offline and runs in a few seconds.

## Rollout

- Ship behind the existing deploy; the endpoint is unused until the dashboard adds the button.
- Set `SUPPLIER_URL` and `SUPPLIER_API_KEY` in the reorder path's environment (already present for price lookups).
- Watch the INFO log for placed orders during the first week and compare against the supplier's billing export.
- No data migration is needed; `init_schema()` creates the table on startup.
