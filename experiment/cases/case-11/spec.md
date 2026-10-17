# Spec: Partial and full refunds for captured orders

**Owner:** Payments squad · **Status:** Approved

## Goal

Support agents currently issue refunds by logging in to the PayCore dashboard, so our order records drift from what was actually refunded. We want `orders-api` to expose a refund endpoint that calls PayCore on the agent's behalf and records every attempt.

## Functional requirements

- **R1.** Add `POST /orders/{order_id}/refunds` with body `{ "amount": "12.50", "note": "optional free text" }`. Amount is in the order's currency.
- **R2.** The amount must be positive, have at most two decimal places, and must not exceed the order's captured amount minus refunds already recorded (pending or succeeded).
- **R3.** The service calls PayCore `POST /v1/refunds` **exactly once** per accepted request. PayCore does not support idempotency keys for refunds, so a repeated call creates a second refund. If the call times out, the refund is recorded with status `pending_review` and the endpoint responds `202`; the finance team reconciles these by hand.
- **R4.** Every attempt is recorded in the `refunds` table with status `succeeded`, `failed`, or `pending_review`, plus the PayCore reference when one is returned.
- **R5.** When PayCore declines a refund, respond `502` with `error.code = "refund_declined"` and an `error.details.reason` that tells the agent why (for example "card expired" or "charge already disputed").
- **R6.** On success respond `201` with `{ "refund_id", "status", "amount", "provider_ref" }`.
- **R7.** Unknown order: `404`. Order not in `captured` status: `409`. Invalid amount: `422`.

## Acceptance criteria

- **AC1.** A valid refund against a captured order returns 201 and a `succeeded` row exists.
- **AC2.** A refund that would exceed the remaining refundable amount returns 422 and PayCore is not called.
- **AC3.** A PayCore timeout produces exactly one outbound call, a `pending_review` row, and a 202.
- **AC4.** A PayCore decline returns 502 with a human-readable `reason`, and a `failed` row exists.
- **AC5.** Errors use the standard `{ "error": { "code", "message", "details" } }` envelope.

## Non-functional constraints

- PayCore decline payloads include the cardholder's billing address, card last4 and card fingerprint. None of these may appear in our logs or API responses.
- Outbound calls must have a timeout; p95 of the endpoint should stay under 1.5 s.
- No new third-party dependencies.

## Out of scope

- Automatic reconciliation of `pending_review` refunds.
- Refunds for orders paid with gift cards.
- Any UI changes in the support console.
