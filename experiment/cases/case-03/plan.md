# Plan: Self-service password reset

## Overview

We add a `PasswordResetService` next to `EmailVerificationService`, two routes in `src/http/routes.ts`, a reset-token store, and a limiter for the request endpoint. Reset tokens are 32 random bytes, sent base64url-encoded in the link and stored only as SHA-256 hashes (`hashToken()` from `src/db/oneTimeTokenRepo.ts`).

## Steps

1. **Migration** (`migrations/0019_password_reset_tokens.sql`, new). Create `password_reset_tokens(token_hash text primary key, user_id uuid not null references users(id) on delete cascade, expires_at timestamptz not null, used_at timestamptz, created_at timestamptz not null default now())` with an index on `user_id`.

2. **Token store** (`src/db/passwordResetTokenRepo.ts`, new). Methods `create(userId, ttlMinutes)`, which returns the raw token, `consume(token)` (an atomic `UPDATE ... WHERE used_at IS NULL AND expires_at > now() RETURNING user_id`), and `invalidateForUser(userId)`, which marks every unused token for the user as used.

3. **Config** (`src/config.ts`). Add `passwordResetTtlMinutes`, read from `PASSWORD_RESET_TTL_MINUTES`, with a default of 60 so that users on slow mail providers aren't caught out.

4. **Mail template** (`src/mail/mailer.ts`). Extend the `Template` union with `"password_reset"`. The template body is managed in the mail provider dashboard and takes a single `link` variable.

5. **Rate limiter** (`src/http/resetLimiter.ts`, new). A sliding-window limiter keyed by normalised email (trimmed and lower-cased) that allows 5 requests per rolling hour. Timestamps are held in a `Map<string, number[]>` and pruned on each call, and the clock is injectable. It exposes `allow(email): boolean` rather than middleware, so a limited request still gets the normal 202.

6. **Service: request** (`src/services/passwordReset.ts`, new). `requestReset(email)`: if `!limiter.allow(email)`, return. Look up the user with `users.findByEmail`; if there is none, return. Otherwise call `invalidateForUser`, then `create(user.id, config.passwordResetTtlMinutes)`, build `${publicBaseUrl}/reset-password?token=...`, `await mailer.send("password_reset", user.email, { link })` on the `HttpMailer` instance, and record `password_reset_requested` with the user id.

7. **Service: confirm** (`src/services/passwordReset.ts`). `confirmReset(token, newPassword)`: check `newPassword.length >= config.passwordMinLength` first and throw `WeakPasswordError` if it is too short, so the token is not consumed (AC6). Then `consume(token)`; if it returns null, throw `InvalidTokenError`. Hash the new password with `argon2.hash`, call `users.updatePasswordHash`, and record `password_reset_completed`.

8. **Routes** (`src/http/routes.ts`). `POST /auth/password-reset/request` checks that `email` is a string, awaits `requestReset`, and returns `202` with no body. `POST /auth/password-reset/confirm` maps `InvalidTokenError` to `400 invalid_token` and `WeakPasswordError` to `400 weak_password`, and returns `204` on success. Error bodies use the existing `{ error: { code, message } }` shape.

9. **Wiring** (`src/server.ts`). Construct `PasswordResetTokenRepo`, the limiter and `PasswordResetService` (users, reset tokens, limiter, mailer, audit, config) next to the existing services, and add `passwordReset` to the `Services` passed to `authRoutes`.

## Test strategy

- `tests/passwordReset.test.ts`, unit tests in the same style as `emailVerification.test.ts`, with mocked repos, limiter and mailer:
  - existing and unknown emails both resolve without throwing, and only the existing one sends mail (AC1);
  - `invalidateForUser` is called before `create` (R4);
  - a limited request sends no mail and records no audit event (R5);
  - a short password throws `WeakPasswordError` and `consume` is not called (AC6);
  - `consume` returning null maps to `InvalidTokenError` (AC2, AC3).
- `tests/resetLimiter.test.ts`: with an injected clock, the sixth call for one email within an hour returns false, and the window slides once the oldest entry is an hour old (AC5).
- Route tests with `supertest` checking that both request variants return 202 with an empty body, and that the confirm route maps each error type to the right status and code.
- A config test that `PASSWORD_RESET_TTL_MINUTES` is parsed as an integer and falls back to the default.

## Rollout and notes

- Deploy the migration first, then the code. The routes are inert until the frontend links to `/reset-password`.
- Publish the `password_reset` template in the provider dashboard before the frontend change ships.
- Frontend: the `/reset-password` page posts the token from the query string and strips it from the URL with `history.replaceState` so that it doesn't linger in browser history.
- Support will get a macro pointing users at the new flow once it is live.
- Security review (SEC-412) will be requested once the PR is up.
