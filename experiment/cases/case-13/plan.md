# Plan: Password reset for authd

## Overview

A new `internal/reset` package owns reset tokens (generation, hashing, storage, verification), request limiting and the two HTTP handlers. Passwords are written through the existing `user.Repo.SetPassword`, so policy and hashing stay in one place. Session revocation is added to the session store so that any future "log out everywhere" feature can reuse it.

## Steps

1. **Migration.** Add `migrations/0012_password_resets.sql` creating `password_resets(token_hash BYTEA PRIMARY KEY, user_id TEXT NOT NULL, expires_at TIMESTAMPTZ NOT NULL, used_at TIMESTAMPTZ)` with an index on `user_id`.

2. **Token store.** `internal/reset/store.go`: `Issue(ctx, userID)` generates 32 random bytes, stores `sha256(token)` with `expires_at = now + 30m`, deletes any earlier unused rows for the user, and returns the URL-safe token. `Lookup(ctx, token)` returns the user ID for a row that is unexpired and unused. `MarkUsed(ctx, token)` sets `used_at = now()`. The SQL sits behind a small `tokenRepo` interface.

3. **Mailer.** `internal/reset/mailer.go`: a small `Mailer` that POSTs the `password_reset` template and link to `MAIL_RELAY_URL` with its own `http.Client` (5 s timeout). The link base comes from `RESET_LINK_BASE`.

4. **Request handler.** `internal/reset/handlers.go` `Request`: decode the email, look up `users.ByEmail`. If the account exists and is enabled, call `store.Issue` and then `mailer.Send` before responding. Unknown or disabled emails skip straight to the response. In every case respond `202` with an empty body. Mailer errors are logged with the recipient and reset link so support can resend it, and do not change the status.

5. **Rate limiting.** `internal/reset/limit.go`: a fixed-window counter keyed by string. The request handler checks it twice before the lookup: `ip:` + `httpx.ClientIP(r)` at 20 per hour and `email:` + lower-cased email at 5 per hour. Over-limit requests get `202` and no email, matching R5.

6. **Confirm handler.** `Confirm`: call `store.Lookup`; on no row return `400 invalid_token`. Call `users.SetPassword`; map `user.ErrWeakPassword` to `422`. On success call `store.MarkUsed`, revoke sessions (step 7) and emit the audit event.

7. **Session revocation.** Add `RevokeAllForUser(ctx, userID string) (int, error)` to the `session.Store` interface. The `RedisStore` implementation iterates with `SCAN` over `sess:*` in batches of 1,000, `GET`s each value, and `DEL`s those whose `user_id` matches. It returns the number removed so we can log it.

8. **Audit.** Emit `password_reset.requested` (user ID only when the account exists, plus IP) and `password_reset.completed` (user ID and IP) via `audit.Emit`.

9. **Configuration.** Read `RESET_LINK_BASE` in `cmd/authd/main.go`, defaulting to `https://account.northwind.app/reset`, and fail startup if it is not an `https` URL.

10. **Wiring.** In `cmd/authd/main.go`, construct the reset store, limiter, mailer and handlers, and register `POST /password-reset/request` and `POST /password-reset/confirm` on the existing mux.

## Test strategy

- `internal/reset/store_test.go`: issue/lookup/mark-used round trip, a used token fails lookup, re-issue invalidates the older token. These run against an in-memory `tokenRepo`.
- `internal/reset/handlers_test.go`: known vs unknown email both return 202 with an empty body (AC1); weak password returns 422; invalid token returns 400; per-email limit stops sending on the sixth request (AC4) and the per-IP limit on the twenty-first, with a stub mailer.
- `internal/reset/limit_test.go`: window rollover and independent keys.
- `internal/session/store_test.go`: `RevokeAllForUser` against miniredis (added as a test-only module), including a user with no sessions.
- AC2 (link in the email works once, and expiry) will be checked manually in staging with a real inbox, since the mailer talks to the real relay.
- AC3 is covered indirectly: revocation is tested at the store level, and `RequireAuth` already rejects missing sessions.

## Rollout and notes

- Security review is booked for the week before launch; the token format and storage will be walked through there.
- The reset page at `account.northwind.app/reset` is being built separately by the frontend team and posts to the confirm endpoint.
- During the first week we will log the number of sessions removed per reset and watch the reset completion rate on the identity dashboard.
