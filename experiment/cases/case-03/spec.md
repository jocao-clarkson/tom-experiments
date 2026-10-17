# Spec: Self-service password reset

**Team:** Identity
**Security review:** required before launch (tracked in SEC-412)

## Goal

Users who forget their password currently have to open a support ticket. We want a standard email-based reset flow that doesn't let anyone find out which emails have accounts and can't be used to flood a user's inbox.

## Functional requirements

- **R1.** `POST /auth/password-reset/request` with `{ "email": string }` always responds `202 Accepted` with an empty body, whether or not an account exists for the email.
- **R2.** If an account exists, issue a single-use reset token valid for **30 minutes** and email a link `{PUBLIC_BASE_URL}/reset-password?token=...` using a new `password_reset` mail template.
- **R3.** `POST /auth/password-reset/confirm` with `{ "token": string, "newPassword": string }` validates the token, checks that the password meets the minimum length policy, updates the password hash, and signs the user out of every existing session.
- **R4.** A reset token can be used once. Requesting a new reset invalidates any earlier outstanding reset tokens for that user.
- **R5.** Rate limits: at most **5** reset requests per email address per hour, and at most **20** per client IP per hour. Requests over the limit still return 202 but send no email.
- **R6.** Write audit events `password_reset_requested` (only when an email is sent) and `password_reset_completed`, each with the user id.

## Acceptance criteria

- **AC1.** Requests for an existing and a non-existing email return identical status and body.
- **AC2.** A token older than 30 minutes is rejected with `400 invalid_token`.
- **AC3.** Reusing a token that has already been used is rejected with `400 invalid_token`.
- **AC4.** After a successful reset, the user's existing refresh sessions no longer work.
- **AC5.** The sixth request for the same email within an hour sends no email, even if requests land on different API instances.
- **AC6.** A password shorter than the configured minimum is rejected with `400 weak_password` and the token is not consumed.

## Non-functional constraints

- Response timing of the request endpoint must not reveal whether an account exists.
- identity-api runs as at least 3 instances behind a round-robin load balancer and is redeployed several times a day.
- No new infrastructure this quarter (no Redis or other shared cache). Postgres is available.
- Raw tokens must never be stored or logged.

## Out of scope

- SMS or authenticator-based recovery.
- Admin-initiated password resets.
- Changes to MFA enrolment.
