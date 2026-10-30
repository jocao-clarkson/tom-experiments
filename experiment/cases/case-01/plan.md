# Plan: Order refunds API

## Overview

We add two endpoints to the orders blueprint, a `create_refund` / `list_refunds` pair on `OrderService`, and a small PayFast refunds client. The `refunds` table and its `insert_refund` / `list_refunds` methods already exist in `repository.py`, so no schema change is needed. Request parsing uses the helpers already in `api.py`, and errors go through the `AppError` hierarchy so the responses match the rest of the service.

## Steps

1. **Request validation** (`orders/api.py`). In the new `POST /orders/<order_id>/refunds` handler, call `require_json_fields(body, {"amount_cents": int, "reason": str})` and `positive_int` on the amount. Add a length check for `reason` (1 to 500 characters, matching the dashboard's note field) that raises `ValidationError` with `details={"reason": "..."}`, so AC4 gets the standard 422 envelope.

2. **Service entry point** (`orders/service.py`). Add `OrderService.create_refund(order_id, amount_cents, reason)`. It loads the order, raises `NotFoundError` if it is missing and `ConflictError(code="invalid_state")` if its status is not `captured`.

3. **PayFast refunds client** (`orders/payfast.py`, new). Add a `PayFastRefunds(base_url, api_key)` class with one method, `create_refund(charge_id, amount_cents)`, that does `requests.post(f"{base_url}/v1/refunds", json={"charge_id": charge_id, "amount": amount_cents}, headers={"Authorization": f"Bearer {api_key}"})` and returns the parsed body. It raises `UpstreamError(code="payment_provider_error")` on any non-2xx status or `requests.RequestException`.

4. **Wiring** (`orders/__init__.py`, `orders/api.py`). `create_app` takes an optional `refunds_client` and stores it in `app.extensions["orders.refunds"]`. When none is given, it builds a `PayFastRefunds` from `config["PAYFAST_BASE_URL"]` and `config["PAYFAST_API_KEY"]`. `_service()` passes it to `OrderService` as a third constructor argument.

5. **Refundable amount check** (`orders/service.py`). In `create_refund`, compute `remaining = order["captured_cents"] - sum(r["amount_cents"] for r in repo.list_refunds(order_id) if r["status"] == "succeeded")`. If `amount_cents > remaining`, raise `ConflictError("refund exceeds captured amount", code="refund_exceeds_capture")` before any call to PayFast (AC2).

6. **Issue and persist** (`orders/service.py`). Call `refunds_client.create_refund(order["charge_id"], amount_cents)`. On success, insert the refund row with `status="succeeded"` and `provider_ref` set to the PayFast refund id, then return the row. If the client raises `UpstreamError`, it propagates to the app's `AppError` handler, which returns the 502 envelope (R5, AC3).

7. **Create endpoint** (`orders/api.py`). The handler calls the service and returns `jsonify(refund), 201`. Refund ids are generated in the service as `ref_` plus `uuid4().hex`.

8. **List endpoint** (`orders/api.py`, `orders/service.py`). Add `GET /orders/<order_id>/refunds`. The service checks that the order exists (404 otherwise) and returns `repo.list_refunds(order_id)`, which already sorts by `created_at DESC` (R6).

9. **Logging** (`orders/service.py`). Log `refund issued` at INFO and `refund failed` at WARNING through `get_logger`, with `order_id`, `refund_id` and `amount_cents` in `extra`. The reason text is not logged.

## Test strategy

- New `tests/test_refunds.py`. Each test builds its app with `create_app(repo, payments, refunds_client=stub)`, using the existing `repo` and `payments` fixtures and a small stub refunds client that records its calls.
- Validation tests: missing `reason`, `reason` too long, boolean and string `amount_cents`, zero and negative amounts (AC4).
- Service tests: the happy path returns 201 and the refund appears in the list (AC1); an amount over the remaining balance returns 409 and the stub records zero calls (AC2); failed refunds inserted with `repo.insert_refund` do not count against the balance.
- 404 and `invalid_state` tests for both endpoints (R7).
- The PayFast timeout and 5xx path (AC3) will be checked by hand against the PayFast sandbox before release, since `payfast.py` calls `requests.post` directly and patching it would need a new test dependency.
- The existing `test_capture.py` is unaffected.

## Rollout and notes

- Internal support agents get the endpoints first through the dashboard; merchant dashboard access follows a week later.
- `PAYFAST_BASE_URL` and `PAYFAST_API_KEY` are already set in every environment for the capture flow, so no new secrets are needed.
- Refunds are rare (a few hundred a day), so the extra `list_refunds` read per request is not a performance concern.
- The dashboard team will consume the `GET` response as-is; its fields are the existing `refunds` columns.
