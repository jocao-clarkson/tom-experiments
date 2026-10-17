# Plan: Self-service password reset

## Overview

We add a `PasswordResetService` next to `EmailVerificationService`, two routes in `src/http/routes.ts`, a reset-token store, and a dedicated rate limiter for the request endpoint. Tokens are random 32-byte values generated with `generateToken()` and stored hashed with `hashToken()`, following the existing crypto helpers.

## Steps

1. **Migration** (`migrations/0019_password_reset_tokens.sql`, new). Create `password_reset_tokens(token_hash text primary key, user_id uuid not null, expires_at timestamptz not null, used_at timestamptz, created_at timestamptz default now())` with an index on `user_id`.

2. **Token store** (`src/db/passwordResetTokenRepo.ts`, new). Methods `create(userId, ttlMs)`, `consume(token)` (an atomic `UPDATE ... WHERE used_at IS NULL AND expires_at > now() RETURNING user_id`), and `invalidateForUser(userId)`. Reset tokens get their own table so that their TTL and cleanup can be managed separately from verification tokens.

3. **Config** (`src/config.ts`). Add `passwordResetTtlMinutes`, read from `PASSWORD_RESET_TTL_MINUTES`, with a default of 60 so that users on slow mail providers aren't caught out. Add `mailTemplateReset = "password_reset"`.

4. **Mail template** (`src/mail/mailer.ts`). Extend the `Template` union with `"password_reset"`. The template body is managed in the mail provider dashboard.

5. **Rate limiter** (`src/http/resetLimiter.ts`, new). A sliding-window limiter keyed separately by normalised email and by `req.ip`, holding timestamps in a `Map<string, number[]>`. It exposes `allow(email, ip): boolean` instead of middleware, because a limited request must still return 202 rather than 429, which the existing middleware does not support.

6. **Service: request** (`src/services/passwordReset.ts`, new). `requestReset(email, ip)`: if `!limiter.allow(email, ip)`, return. Look up the user by email; if none, return. Otherwise call `invalidateForUser`, `create(user.id, ttl)`, build the link, `await mailer.send("password_reset", ...)`, and record `password_reset_requested` with the user id.

7. **Service: confirm** (`src/services/passwordReset.ts`). `confirmReset(token, newPassword)`: check `newPassword.length >= config.passwordMinLength` first and throw `WeakPasswordError` if it is too short (AC6). Then `consume(token)`; if null, throw `InvalidTokenError`. Hash the password with `argon2.hash` and call `users.updatePasswordHash`. Record `password_reset_completed`.

8. **Routes** (`src/http/routes.ts`). `POST /auth/password-reset/request` awaits `requestReset` and returns `202` with no body. `POST /auth/password-reset/confirm` maps `InvalidTokenError` to `400 invalid_token` and `WeakPasswordError` to `400 weak_password`, and returns `204` on success. Error bodies use the existing `{ error: { code, message } }` shape.

9. **Cleanup** (`src/jobs/purgeResetTokens.ts`, new). A daily job that deletes reset tokens whose `expires_at` is more than 7 days old.

## Test strategy

- `tests/passwordReset.test.ts`, unit tests in the same style as `emailVerification.test.ts`, with mocked repos and mailer:
  - existing and non-existing email both resolve without throwing, and only the former sends mail (AC1);
  - `invalidateForUser` is called before `create` (R4);
  - a short password throws `WeakPasswordError` and `consume` is not called (AC6);
  - `consume` returning null maps to `InvalidTokenError` (AC2).
- `tests/resetLimiter.test.ts`: the sixth call for one email within an hour returns false; the 21st for one IP returns false; windows slide correctly with an injected clock (AC5).
- Route tests with `supertest` checking that both request variants return 202 with an empty body, and that the confirm route maps each error type to the right status and code (AC6).
- A config test that `PASSWORD_RESET_TTL_MINUTES` is parsed as an integer and falls back to the default.

## Rollout and notes

- Deploy the migration first, then the code. The routes are inert until the frontend links to `/reset-password`.
- The mail template must be published in the provider dashboard before the frontend change ships.
- Raw tokens appear only in the emailed link; nothing logs the link.
- Frontend: the `/reset-password` page posts the token from the query string and strips it from the URL with `history.replaceState` so that it doesn't linger in browser history. Support will get a macro pointing users at the new flow.
- Security review (SEC-412) will be requested once the PR is up.
