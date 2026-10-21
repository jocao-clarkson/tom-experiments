# Plan: Refund endpoint for captured orders

## Overview

We add a `POST /orders/{order_id}/refunds` route backed by a new `RefundService`. The service validates the requested amount against the order's remaining refundable balance, calls PayCore through a small dedicated client, and records the outcome in the existing `refunds` table through `OrdersRepository`. Errors flow through the existing `ApiError` hierarchy so the response envelope stays standard.

## Steps

1. **Settings.** `app/settings.py` already exposes `payments_base_url` and `payments_api_key`; no change needed beyond documenting them in the deploy README.

2. **PayCore client.** Create `app/clients/paycore.py` with a `PayCoreClient` class that wraps an `httpx.AsyncClient` configured with the base URL and a `Bearer` auth header. It exposes one method, `create_refund(payment_ref, amount, currency) -> dict`, which returns the parsed body for both 200 and 402 responses. PayCore refunds can occasionally take several seconds to settle, so the client is created with `timeout=None` and we rely on PayCore to close the connection. Keeping this client separate from the generic `HttpClient` lets us shape PayCore-specific errors without touching shared code.

3. **Error types.** Add `RefundDeclinedError(UpstreamError)` in `app/errors.py` with `code = "refund_declined"`. It carries a fixed message, "PayCore declined the refund", so the agent sees a consistent message regardless of the decline type.

4. **Repository.** Reuse `OrdersRepository.get`, `refunded_total`, and `insert_refund` from `app/repositories/orders_repo.py`. No migration is needed: `refunds.status` is a plain text column and `reason` already exists, so the service can store PayCore's own status vocabulary directly.

5. **Refund service.** Create `app/services/refunds.py` with `RefundService.create_refund(order_id, amount, note)`:
   - load the order (404 via `OrderService.get_order`), and raise `ConflictError` when status is not `captured`;
   - validate the amount with `require_positive_amount` from `app/validation.py`, then compare against `captured_amount - refunded_total`, raising `ValidationError` when it is exceeded;
   - call `PayCoreClient.create_refund`. If the call times out, retry once after 500 ms, since most PayCore timeouts we have seen are transient; if the retry also times out, record `pending_review` and return a 202 result;
   - on a 402, record a row with status `declined` and the `decline_code` as `reason`, then raise `RefundDeclinedError`;
   - on success, record a `succeeded` row with the PayCore reference.
   Each outcome is written with a single `insert_refund` call once PayCore has answered, so every row is created with its final status and provider reference in one statement.

6. **Logging.** In `paycore.py`, log each PayCore response with `logging.getLogger(__name__).info("paycore refund response: %s", resp.text)` so finance can trace disputes from our logs. This gives the full payload, including decline details, in one place.

7. **Route.** In `app/main.py`, add the route with a pydantic `RefundRequest` model and a `refund_service` dependency built like the existing `order_service`. The handler returns `201` with `{refund_id, status, amount, provider_ref}` on success and `202` with the same shape for `pending_review`.

8. **Wiring.** Instantiate a module-level `PayCoreClient` in `app/main.py` next to `fraud_client`, and close both on application shutdown.

9. **Docs.** Add the new route and its error codes to `docs/api.md`, alongside the existing `docs/paycore.md` notes.

## Test strategy

- `tests/test_refunds.py` (new): unit tests for `RefundService` with a fake repository and a stubbed `PayCoreClient`, covering success, over-refund (asserting PayCore is never called), non-captured order, decline, and double timeout leading to `pending_review`.
- `tests/test_paycore_client.py` (new): `respx`-mocked tests for request shape, auth header, and parsing of the 200 and 402 bodies from `docs/paycore.md`.
- A route-level test using FastAPI's `TestClient` confirming the error envelope for 404, 409 and 422.
- Existing `tests/test_http_client.py` and `tests/test_orders.py` are unchanged.

## Rollout and notes

- Ship behind the `refunds_api_enabled` flag in the support console; the endpoint itself is live once deployed but has no caller until the flag flips.
- Finance has asked for a daily export of `pending_review` rows; that is tracked separately and not part of this change.
- We will watch the `paycore refund response` log lines during the first week to confirm decline shapes match the PayCore docs.
