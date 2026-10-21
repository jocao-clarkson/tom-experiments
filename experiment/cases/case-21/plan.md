# Plan: Item reorder endpoint

## Overview

We add a `reorders` table to the existing SQLite schema, a `reorder` method on `InventoryService`, and a `POST /items/<sku>/reorder` route. Purchase orders are placed through a small `inventory/purchase_orders.py` module. Errors are raised as the existing `APIError` subclasses so the response shape stays consistent with the rest of the API.

## Steps

1. **Schema.** In `inventory/repository.py`, extend `init_schema()` with a `reorders` table: `id INTEGER PRIMARY KEY`, `sku TEXT NOT NULL`, `quantity INTEGER NOT NULL`, `supplier_po_id TEXT NOT NULL`, `status TEXT NOT NULL DEFAULT 'pending'`, `created_at TEXT NOT NULL`, plus `UNIQUE (sku, status)`. Add `create_reorder(sku, quantity, po_id)`, which stamps `created_at` with `StockRepository.now()` and returns the new row, and `get_pending_reorder(sku)`, which selects the row with `status = 'pending'` that passes `within_hours("created_at", 24)`, or returns `None`.

2. **Request schema.** In `inventory/routes.py`, add `REORDER_SCHEMA = {"quantity": {"type": int, "required": True, "min": 1, "max": 1000}}` next to `ADJUST_SCHEMA`, validated through `validate_payload` so unknown fields are rejected the same way as `/adjust`.

3. **Purchase-order module.** Create `inventory/purchase_orders.py` with `place_purchase_order(sku, quantity) -> str`. It reads `SUPPLIER_URL` and `SUPPLIER_API_KEY`, sends `requests.post(f"{url}/purchase-orders", json={"sku": sku, "quantity": quantity}, headers={"Authorization": f"Bearer {key}"}, timeout=10)`, and returns the `id` from the response body. The call runs in a loop of up to 3 attempts with 1s then 2s backoff on `ConnectionError`, `Timeout` and 5xx responses.

4. **Service method.** Add `InventoryService.reorder(sku, quantity)` in `inventory/service.py`: call `get_item(sku)` for the 404 case, call `repo.get_pending_reorder(sku)` and raise `Conflict` if a row comes back, call `place_purchase_order`, then `repo.create_reorder(...)`. An `sqlite3.IntegrityError` from the `UNIQUE (sku, status)` constraint is caught and raised as `Conflict`, so two concurrent requests for the same SKU end with a single pending row (AC5). Return a dict with `reorder_id`, `supplier_po_id` and `status`.

5. **Error mapping.** In `place_purchase_order`, raise `UpstreamError` once the attempts are used up or the supplier returns a 4xx, with the supplier status in `details`. The row is only written after the supplier call returns, so a failure leaves no `reorders` row (R6).

6. **Route.** Add `@bp.post("/items/<sku>/reorder")` in `inventory/routes.py` that validates the body with `REORDER_SCHEMA`, calls `_service().reorder(sku, body["quantity"])`, and returns `jsonify(result), 202`.

7. **Logging.** In `InventoryService.reorder`, log each placed order at INFO with `sku`, `quantity` and `supplier_po_id` through a module-level `logging.getLogger(__name__)`.

8. **Test dependency.** Add `freezegun` to the `dev` extra in `pyproject.toml` so the stale-reorder test can move the clock forward.

9. **Tests.** Add `tests/test_reorder.py` (details below). `tests/test_routes.py` and `tests/conftest.py` stay as they are.

10. **Docs.** Add the endpoint, request body, response body and error codes (400, 404, 409, 502) to the API section of the service runbook so the dashboard team can integrate.

## Test strategy

All new tests live in `tests/test_reorder.py`, use the existing `client` fixture, and replace `inventory.purchase_orders.requests.post` with a `monkeypatch` stub that records its calls and returns a scripted response or raises a scripted exception. Nothing leaves the process.

- Validation: quantity `0`, the string `"5"`, and an extra field each return 400 `validation_failed` (AC1).
- Happy path: stub returns `{"id": "PO-1"}`; assert 202, the three body fields, one stub call, and one row in `reorders` (AC2).
- Supplier timeout: stub raises `requests.Timeout`; assert 502 `upstream_error` and no row in `reorders` (AC3).
- Pending conflict: insert a pending row directly, assert 409 and that the stub was not called (AC4).
- Concurrency: send two requests from two threads against the same SKU and assert exactly one row in `reorders` (AC5).
- Stale pending: place a reorder, then inside `freeze_time` 25 hours later place another; assert 202 and two rows (AC6).
- Unknown SKU returns 404 `not_found` (R2).


## Rollout

- Ship with the regular deploy; the endpoint is unused until the dashboard adds the button.
- `SUPPLIER_URL` and `SUPPLIER_API_KEY` are already set in every environment for price lookups.
- No data migration is needed; `init_schema()` creates the table on startup.
- During the first week, compare the INFO log of placed orders against the supplier's billing export.
