# Plan: Password reset for authd

## Overview

A new `internal/reset` package owns reset tokens (generation, hashing, storage, verification) and the two HTTP handlers. Passwords are written through the existing `user.Repo.SetPassword`, so policy and hashing stay in one place. Session revocation is added to the session store so that any future "log out everywhere" feature can reuse it.

## Steps

1. **Migration.** Add `migrations/0012_password_resets.sql` creating `password_resets(token_hash BYTEA PRIMARY KEY, user_id TEXT NOT NULL, expires_at TIMESTAMPTZ NOT NULL, used_at TIMESTAMPTZ)` with an index on `user_id`.

2. **Token store.** `internal/reset/store.go`: `Issue(ctx, userID)` generates 32 random bytes, stores `sha256(token)` with `expires_at = now + 1h`, deletes any earlier unused rows for the user, and returns the URL-safe token. `Consume(ctx, token)` runs `UPDATE ... SET used_at = now() WHERE token_hash = $1 AND used_at IS NULL AND expires_at > now() RETURNING user_id` so a token can only be consumed once even under concurrent confirms.

3. **Mailer.** `internal/reset/mailer.go`: a small `Mailer` that POSTs the `password_reset` template and link to `MAIL_RELAY_URL` with its own `http.Client` (5 s timeout). Keeping it in the reset package avoids coupling the reset flow to the generic queue's drop-on-full behaviour, which is not acceptable for a user-initiated email.

4. **Request handler.** `internal/reset/handlers.go` `Request`: decode the email, look up `users.ByEmail`. If the account exists and is enabled, call `store.Issue` and then `mailer.Send` before responding. Unknown or disabled emails skip straight to the response. In every case respond `202` with an empty body; mailer errors are logged and swallowed so they do not change the status.

5. **Rate limiting.** Wrap the request route in `httpx.RateLimit(httpx.ClientIP, 20, time.Hour, ...)` for the per-IP limit. For the per-email limit, the handler keeps its own map keyed by lower-cased email using the same fixed-window approach, checked before the lookup; over-limit emails get `202` and no email.

6. **Confirm handler.** `Confirm`: call `store.Consume`; on no row return `400 invalid_token`. Call `users.SetPassword`; map `user.ErrWeakPassword` to `422`. Then revoke sessions (step 7) and emit the audit event.

7. **Session revocation.** Add `RevokeAllForUser(ctx, userID string) (int, error)` to the `session.Store` interface. The `RedisStore` implementation iterates with `SCAN` over `sess:*` in batches of 1,000, `GET`s each value, and `DEL`s those whose `user_id` matches. It returns the number removed so we can log it.

8. **Audit.** Emit `password_reset.requested` (user ID only when the account exists, plus IP) and `password_reset.completed` via `audit.Emit`.

9. **Wiring.** In `cmd/authd/main.go`, construct the reset store, mailer and handlers, and register `POST /password-reset/request` and `POST /password-reset/confirm`.

## Test strategy

- `internal/reset/store_test.go`: issue/consume round trip, second consume fails, re-issue invalidates the older token. The store's SQL sits behind a small `tokenRepo` interface so these tests run against an in-memory implementation.
- `internal/reset/handlers_test.go`: known vs unknown email both return 202 with an empty body (AC1); weak password returns 422; invalid token returns 400; per-email limit stops sending on the sixth request (AC4), with a stub mailer.
- `internal/session/store_test.go`: `RevokeAllForUser` against miniredis, including a user with no sessions.
- AC2 (link in the email works once, and expiry) will be checked manually in staging with a real inbox, since the mailer talks to the real relay.
- AC3 is covered indirectly: revocation is tested at the store level, and `RequireAuth` already rejects missing sessions.

## Rollout and notes

- Security review is booked for the week before launch; the token format and storage will be walked through there.
- The reset link points at `https://account.northwind.app/reset?token=...`; the frontend page is being built separately.
- We expect revocation to touch only a handful of sessions per user, so the SCAN cost should be acceptable; we will log the duration of each call during the first week.
