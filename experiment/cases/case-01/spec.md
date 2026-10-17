# Spec: Order refunds API

**Owner:** Payments & Orders team
**Status:** Approved for build

## Goal

Support agents and the merchant dashboard currently issue refunds by logging into the PayFast console, so our order records drift from what the provider actually refunded. We want a first-class refunds API on the orders service that issues the refund through PayFast and keeps an auditable refund history on the order.

## Functional requirements

- **R1.** Add `POST /orders/{order_id}/refunds` accepting a JSON body `{ "amount_cents": int, "reason": string }`. Both fields are required; `reason` is 1 to 280 characters.
- **R2.** `amount_cents` must be positive and must not exceed the order's `captured_cents` minus the sum of all of the order's refunds with status `succeeded`. A request that would exceed this returns 409 with code `refund_exceeds_capture`.
- **R3.** The service issues the refund by calling PayFast `POST /v1/refunds` with the order's `charge_id` and the amount.
- **R4.** Every refund attempt is persisted in the `refunds` table with status `succeeded` or `failed`, the reason, and the PayFast refund id when one is returned.
- **R5.** If PayFast returns an error or does not respond, the refund is recorded as `failed` and the API returns 502 with code `payment_provider_error`.
- **R6.** Add `GET /orders/{order_id}/refunds` returning the order's refunds, newest first.
- **R7.** Unknown orders return 404; orders that are not in `captured` status return 409 with code `invalid_state`.

## Acceptance criteria

- **AC1.** A valid refund on a captured order returns 201 with the refund record, and `GET /orders/{id}/refunds` lists it.
- **AC2.** A refund larger than the remaining refundable amount returns 409 `refund_exceeds_capture` and PayFast is not called.
- **AC3.** When PayFast returns 5xx or times out, the API returns 502 `payment_provider_error` and a `failed` refund row exists.
- **AC4.** A body missing `reason`, or with a non-integer amount, returns 422 using the standard error envelope.
- **AC5.** Two refunds issued concurrently against the same order can never together exceed the captured amount.

## Non-functional constraints

- PayFast's refund endpoint does **not** support idempotency keys. Sending the same refund request twice issues two refunds.
- The refund request must complete, success or failure, within 10 seconds in the worst case.
- Use the existing error envelope and logging conventions. No new third-party runtime dependencies.
- Tests must run offline in CI.

## Out of scope

- Line-item or partial-quantity refunds.
- Customer email notifications.
- Reversing or cancelling a refund.
