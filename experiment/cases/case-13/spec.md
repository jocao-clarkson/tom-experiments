# Spec: Self-service password reset

**Area:** Identity (`authd`) · **Security review:** required before launch

## Goal

Users who forget their password currently have to contact support. We will add an email-based password reset to `authd` that does not leak which emails have accounts and that cuts off anyone holding the old credentials.

## Functional requirements

- **R1.** `POST /password-reset/request` with `{ "email" }` always responds `202` with an empty body, whether or not the email belongs to an account (or the account is disabled).
- **R2.** For an existing, enabled account, send a `password_reset` email containing a link with a single-use reset token. The token is valid for **30 minutes**. Requesting again issues a new token and invalidates any earlier one.
- **R3.** `POST /password-reset/confirm` with `{ "token", "new_password" }` sets the new password if the token is valid, unexpired and unused, then marks the token used. Invalid, expired or used tokens return `400` with `{ "error": "invalid_token" }`. A new password that fails the existing password policy returns `422`.
- **R4.** A successful reset must end **every** existing session for that user on all devices, effective immediately.
- **R5.** Rate limits on `/password-reset/request`: 5 per hour per email address and 20 per hour per client IP. Over-limit requests still return `202` but send nothing.
- **R6.** Emit audit events `password_reset.requested` and `password_reset.completed` (with user ID when known and client IP).

## Acceptance criteria

- **AC1.** Request for a known and an unknown email both return 202 with identical bodies.
- **AC2.** The email for a known account contains a link whose token works once, and fails with `invalid_token` after 30 minutes.
- **AC3.** After a successful confirm, a request using a session cookie issued before the reset gets `401`.
- **AC4.** A sixth request for the same email within an hour sends no email.
- **AC5.** A confirm whose new password fails the policy returns `422`, and the same link then succeeds with a valid password.

## Non-functional constraints

- The raw reset token appears only in the emailed link. Persist only its SHA-256 hash.
- Response time of the request endpoint must not reveal whether an account exists; mail delivery must not happen on the request path.
- Use the existing password policy and password storage (`Repo.SetPassword`).
- Production Redis holds about 4 million live sessions; avoid operations that scale with the total number of sessions.
- `go test ./...` must not require network access or external services.

## Out of scope

- Reset via SMS or security questions.
- Admin-initiated resets.
- Changes to the login flow or session lifetime.
