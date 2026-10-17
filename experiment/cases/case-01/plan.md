# Plan: Order refunds API

## Overview

We add two endpoints to the orders blueprint, a `create_refund` / `list_refunds` pair on `OrderService`, and a small PayFast refunds client. The `refunds` table already exists in `repository.py`, so no schema change is needed. Validation and error handling go through the existing `validation.py` helpers and the `AppError` hierarchy so the responses match the rest of the service.

## Steps

1. **Request validation** (`orders/api.py`). In the new `POST /orders/<order_id>/refunds` handler, call `require_json_fields(body, {"amount_cents": int, "reason": str})` and `positive_int` on the amount. Add a length check for `reason` (1 to 280 characters) that raises `ValidationError` with `details={"reason": "..."}` so AC4 gets the standard 422 envelope.

2. **Service entry point** (`orders/service.py`). Add `OrderService.create_refund(order_id, amount_cents, reason)`. It loads the order, raises `NotFoundError` if missing and `ConflictError(code="invalid_state")` if the status is not `captured`.

3. **PayFast refunds client** (`orders/payfast.py`, new). Add a `PayFastRefunds` class with one method, `create_refund(charge_id, amount_cents)`, that does `requests.post(f"{base_url}/v1/refunds", json=..., headers={"Authorization": f"Bearer {api_key}"})` and returns the parsed body. Keeping it separate from the generic client keeps the refund call simple and makes it obvious that it is a single call. It raises `UpstreamError(code="payment_provider_error")` on any non-2xx status or `requests.RequestException`.

4. **Wiring** (`orders/__init__.py`). `create_app` takes an optional `refunds_client`; when not given, it builds a `PayFastRefunds` from `config["PAYFAST_BASE_URL"]` and `config["PAYFAST_API_KEY"]`. The service gets it as a third constructor argument.

5. **Refundable amount check** (`orders/service.py`). In `create_refund`, compute `remaining = order["captured_cents"] - sum(r["amount_cents"] for r in repo.list_refunds(order_id) if r["status"] == "succeeded")`. If `amount_cents > remaining`, raise `ConflictError("refund exceeds captured amount", code="refund_exceeds_capture")` before any call to PayFast (AC2).

6. **Issue and persist** (`orders/service.py`). Call `refunds_client.create_refund(order["charge_id"], amount_cents)`. On success, insert the refund row with `status="succeeded"` and `provider_ref` set to the PayFast refund id, then return the row. If the client raises `UpstreamError`, let it propagate to the blueprint error handler, which returns the 502 envelope (R5, AC3).

7. **Create endpoint** (`orders/api.py`). The handler calls the service and returns `jsonify(refund), 201`. Refund ids are generated in the service as `ref_` plus `uuid4().hex`.

8. **List endpoint** (`orders/api.py`, `orders/service.py`). Add `GET /orders/<order_id>/refunds`. The service checks that the order exists (404 otherwise) and returns `repo.list_refunds(order_id)`, which already sorts by `created_at DESC` (R6).

9. **Logging** (`orders/service.py`). Log `refund issued` and `refund failed` at INFO and WARNING through `get_logger`, with `order_id`, `refund_id` and `amount_cents` in `extra`. No body content is logged.

## Test strategy

- New `tests/test_refunds.py` using the existing Flask `client` and `repo` fixtures.
- Unit tests for validation: missing `reason`, `reason` too long, boolean and string `amount_cents`, zero and negative amounts (AC4).
- Service tests with a stub `refunds_client` passed to `create_app`: happy path returns 201 and appears in the list (AC1); amount over the remaining balance returns 409 and the stub records zero calls (AC2); previously failed refunds do not count against the balance.
- 404 and `invalid_state` tests for both endpoints (R7).
- The PayFast timeout and 5xx path (AC3) will be checked manually against the PayFast sandbox before release, because mocking `requests` directly in `payfast.py` would need a new test dependency.
- Existing `test_capture.py` is unaffected.

## Rollout and notes

- Ship behind the `refunds_api_enabled` flag in config, defaulting to off in production. The dashboard team will turn it on for internal agents first.
- `PAYFAST_BASE_URL` and `PAYFAST_API_KEY` are already set in every environment for the capture flow, so no new secrets are needed.
- Refunds are rare (a few hundred a day), so the extra `list_refunds` read per request is not a performance concern.
- If PayFast latency becomes a problem, we can move refund issuing to a background job later; that is not needed for this release.
