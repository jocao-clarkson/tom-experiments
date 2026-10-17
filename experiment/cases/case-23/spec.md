# Spec: Self-service password reset

## Goal

Support tickets for locked-out users are our largest support category. Let users reset their password by email without contacting support, without making account enumeration or token theft easier.

## Functional requirements

- **R1.** `POST /auth/password-reset/request` with `{"email"}` always returns 202 `{"status": "ok"}`, whether or not an account exists. If it exists, create a reset token and enqueue the `password_reset` email containing the link.
- **R2.** Tokens are 32 random bytes, stored only as a SHA-256 hash in a new `password_resets` table (`user_id`, `token_hash`, `expires_at`, `used_at`, `created_at`). They expire 30 minutes after creation and can be used once. Issuing a new token invalidates the user's earlier unused tokens.
- **R3.** `POST /auth/password-reset/confirm` with `{"token", "newPassword"}`. An unknown, expired, or already-used token returns 400 `invalid_token` (one code for all three). A password failing the existing policy returns 400 `weak_password` with the policy errors.
- **R4.** On success: update the password hash, mark the token used, and revoke all of the user's sessions.
- **R5.** Rate limits on `request`: at most 5 per email per hour and 20 per IP per hour. Over the IP limit returns 429. Over the email limit still returns 202 but sends nothing. The per-email limit must hold across the whole deployment; the per-IP limit is best-effort.
- **R6.** Log `password_reset_completed` with the user id on success.

## Acceptance criteria

- **AC1.** An unknown email returns the same 202 body as a known one and enqueues no email.
- **AC2.** No raw token is ever persisted.
- **AC3.** A token used twice fails the second time with `invalid_token`; two concurrent confirms with the same token result in exactly one password change.
- **AC4.** A token 31 minutes old returns `invalid_token`.
- **AC5.** A sixth request for the same email within an hour enqueues no email, whichever replica serves it.
- **AC6.** After a reset, previously issued session tokens are rejected.

## Non-functional constraints

- The service runs as 3 replicas behind the load balancer. Postgres is the only datastore; no new infrastructure (Redis, managed queues) this quarter.
- CI runners have no Docker. Service and route tests run against the in-memory fakes in `test/fakes.ts`.
- Tokens and passwords must never appear in logs.

## Out of scope

- Changing the login flow or session format.
- SMS or authenticator-based recovery.
- Email template design (handled by the comms team).
