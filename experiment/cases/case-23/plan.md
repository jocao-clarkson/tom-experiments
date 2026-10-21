# Plan: Self-service password reset

## Overview

Add a `PasswordResetService` next to `AuthService`, a `ResetRepo` backed by a new `password_resets` table, two routes in `src/routes/auth.ts`, and a Redis-backed limiter for the request endpoint. Email goes through the existing `Mailer.enqueue`, and audit lines use the shared `logger`.

## Steps

1. **Migration.** Add `migrations/014_password_resets.sql` creating `password_resets (id uuid pk default gen_random_uuid(), user_id uuid not null references users, token text not null unique, expires_at timestamptz not null, used_at timestamptz, created_at timestamptz not null default now())` and an index on `(user_id, created_at)`.

2. **Repository.** Add `ResetRepo` to `src/repos/types.ts` with `create(userId, token, expiresAt)`, `findByToken(token)`, `markUsed(id)`, and `invalidateOpenForUser(userId)`. Implement `PgResetRepo` in `src/repos/pg.ts` and `FakeResetRepo` in `test/fakes.ts`. The token is stored as issued so `findByToken` is a plain indexed equality lookup; `generateToken` gives 256 bits of entropy, so the stored value is not guessable.

3. **Limiter.** Add `ioredis` and `src/lib/redisLimiter.ts`, an `INCR` + `EXPIRE` fixed-window counter whose `hit(key)` returns the same `LimitResult` as `FixedWindowLimiter`, so routes handle both the same way.

4. **Request flow.** `PasswordResetService(users, sessions, resets, mailer, limiter, now)` in `src/services/passwordResetService.ts`. `request(email, ip)`: hit `reset-ip:<ip>` (20 per hour) and throw `AuthError("rate_limited", 429)` with the retry delay when over. Look up the user; if none, throw `AuthError("account_not_found", 404)` so the web client can ask the user to check the address. Otherwise call `invalidateOpenForUser`, create a token with `generateToken()`, store it with `expiresAt = this.now() + 30 min`, and `mailer.enqueue("password_reset", user.email, { link })` with `link = ${RESET_LINK_BASE}?token=<token>`.

5. **Confirm flow.** `confirm(token, newPassword)`: run `validatePassword` and throw `weak_password` with its errors. Call `findByToken` and throw `invalid_token` if the row is missing, `expiresAt <= this.now()`, or `usedAt` is set. Then `bcrypt.hash` the new password (cost 12), `users.updatePasswordHash`, `resets.markUsed(id)`, and `sessions.revokeAllForUser(userId)`.

6. **Error details.** Give `AuthError` an optional `details: string[]`, and have the auth route mapper add `errors: details` to the body when present. Login errors carry no details, so their responses are unchanged.

7. **Routes.** In `src/routes/auth.ts`, add `POST /auth/password-reset/request` reading `{ email }` and returning 202 `{status: "ok"}` (429 with `Retry-After` when limited), and `POST /auth/password-reset/confirm` reading `{ token, newPassword }` and returning 204. Unexpected errors go to `next(err)`, as in the login route.

8. **Audit log.** On successful confirm, `logger.info("password_reset_completed", { userId })`. Failed confirms log `password_reset_failed` with the error code, so support can spot users stuck in a loop.

9. **Wiring.** In `src/server.ts`, create the Redis client from `REDIS_URL`, construct `RedisLimiter`, `PgResetRepo`, and `PasswordResetService` with the existing mailer, and pass the service and limiter to `authRouter`.

10. **Config.** Add `REDIS_URL` and `RESET_LINK_BASE` to the deployment manifests for all three replicas.

## Test strategy

- `test/passwordReset.test.ts` (vitest, fakes): a request for a known email enqueues one `password_reset` mail with a link; a weak password returns `weak_password` with the policy errors; a successful confirm changes the hash and revokes sessions (AC6), and a second confirm with the same token returns `invalid_token`.
- `test/redisLimiter.test.ts`: runs the limiter against a small in-memory stand-in for the ioredis client added to `test/fakes.ts`; it allows 20 hits, blocks the 21st, and reports the retry delay.
- Log tests are not needed: the shared logger already redacts credential fields, and the new lines carry only ids and codes.
- `test/auth.test.ts` stays as is; the login path is untouched apart from the optional `details` field.

## Rollout

- Provision a small Redis instance in the identity namespace before deploy.
- Ship the endpoints dark; enable the "Forgot password?" link in the web client after one day of monitoring 4xx/5xx rates.
- Alert if `password_reset_completed` exceeds 3x the weekly baseline.
