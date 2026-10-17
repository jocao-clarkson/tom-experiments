# Plan: Self-service password reset

## Overview

Add a `PasswordResetService` next to `AuthService`, a `ResetRepo` backed by a new `password_resets` table, two routes in `src/routes/auth.ts`, and a shared rate limiter so limits hold across all three replicas. Email goes through the existing `Mailer.enqueue`, and logging uses the redacting `logger`.

## Steps

1. **Migration.** Add `migrations/014_password_resets.sql` creating `password_resets (id uuid pk, user_id uuid fk, token text unique, expires_at timestamptz, used_at timestamptz null, created_at timestamptz default now())` and an index on `(user_id, created_at)`.

2. **Repository.** Add `ResetRepo` to `src/repos/types.ts` with `create(userId, token, expiresAt)`, `findByToken(token)`, `markUsed(id)`, and `invalidateOpenForUser(userId)`. Implement `PgResetRepo` in `src/repos/pg.ts` and a `FakeResetRepo` in `test/fakes.ts`. The token is stored as issued so `findByToken` is a plain indexed equality lookup; `generateToken` already gives 256 bits of entropy, so the stored value is not guessable.

3. **Shared limiter.** Add `ioredis` and `src/lib/redisLimiter.ts` with an `INCR` + `EXPIRE` fixed-window counter exposing the same `hit(key)` shape as `FixedWindowLimiter`. Redis gives one counter for all replicas.

4. **Request flow.** `PasswordResetService.request(email, ip)`: hit `reset-ip:<ip>` on the Redis limiter (20/hour), returning a rate-limit error when exceeded. Look up the user. If none, throw `AuthError("account_not_found", 404)` so the client can tell the user to check the address. Otherwise call `invalidateOpenForUser`, create a token with `generateToken()`, store it with `expiresAt = now + 30 min`, and `mailer.enqueue("password_reset", user.email, { link })`. The link is `${RESET_LINK_BASE}?token=<token>`; since `enqueue` never blocks on SMTP, request latency stays flat.

5. **Confirm flow.** `PasswordResetService.confirm(token, newPassword)`: run `validatePassword` and throw `weak_password` with its errors. Call `findByToken`, and throw `invalid_token` if missing, expired, or `used_at` is set. Then `bcrypt.hash` the new password, `users.updatePasswordHash`, `resets.markUsed(id)`, and `sessions.revokeAllForUser(userId)`.

6. **Clock.** Pass the same `now: () => Date` to `PasswordResetService` as `AuthService` takes, so expiry is computed from one source.

7. **Routes.** In `src/routes/auth.ts`, add `POST /auth/password-reset/request` (202 `{status: "ok"}`) and `POST /auth/password-reset/confirm` (204), mapping `AuthError` to `{ error: code }` with its status, as the login route does.

8. **Audit log.** On successful confirm, `logger.info("password_reset_completed", { userId })`. Failed confirms log `password_reset_failed` with the error code only, never the submitted token, so support can spot users stuck in a loop.

9. **Wiring.** Construct the Redis client from `REDIS_URL` in `src/server.ts` and inject the limiter and `PgResetRepo`.

10. **Config.** Add `REDIS_URL` and `RESET_LINK_BASE` to the deployment manifests for all three replicas.

## Test strategy

- `test/passwordReset.test.ts` (vitest, fakes): request for a known email enqueues one `password_reset` mail; weak password returns `weak_password` with errors; successful confirm revokes sessions (AC6) and a second confirm with the same token returns `invalid_token`.
- `test/redisLimiter.test.ts`: limiter allows 20 and blocks the 21st within a window.
- `test/integration/reset.pg.test.ts`: run the full request/confirm flow against Postgres and Redis in `testcontainers` to check the migration and SQL, and that the stored token round-trips.
- Logger redaction already covers `token` and `newPassword`, so log tests are not needed.
- Existing `test/auth.test.ts` stays as is; the login path is untouched.

## Rollout

- Provision a small Redis instance for the identity namespace before deploy.
- Ship the endpoints dark; enable the "Forgot password?" link in the web client after one day of monitoring 4xx/5xx rates.
- Alert if `password_reset_completed` exceeds 3x the weekly baseline.
