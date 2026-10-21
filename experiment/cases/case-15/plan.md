# Plan: Notification inbox endpoints

## Overview

We add a `notificationsRouter` mounted at `/v1/notifications` behind `requireUser`, with a thin `NotificationsRepo` holding the SQL. The table already exists and is populated by the producing services, so the work is four endpoints, one migration for indexes, and tests.

## Steps

1. **Migration.** `migrations/1729000000000_notifications_inbox_indexes.sql`:
   - `CREATE INDEX CONCURRENTLY notifications_user_created_idx ON notifications (user_id, created_at DESC, id DESC);`
   - `CREATE INDEX CONCURRENTLY notifications_user_unread_idx ON notifications (user_id) WHERE read_at IS NULL;`
   The partial index keeps `unread-count` an index-only count over a user's unread rows, which is what the 50 ms budget needs.

2. **Repository.** New `src/db/notificationsRepo.ts` with `list(userId, offset, limit)`, `unreadCount(userId)`, `markRead(id)`, and `markAllRead(userId)`. Each method is one parameterised statement issued through `query` from `src/db/pool.ts`; routes never build SQL themselves.

3. **Paging for the inbox.** New `src/lib/inboxCursor.ts`. The inbox cursor is an opaque base64url string wrapping the offset of the next page, which keeps the client contract identical to other list endpoints (`{ items, nextCursor }`, opaque string) while letting us use a simple `WHERE user_id = $1 ORDER BY created_at DESC, id DESC OFFSET $2 LIMIT $3` query. `limit` defaults to 20 and is capped at 100.

4. **List endpoint.** `src/routes/notifications.ts` `GET /`: parse `limit` and `cursor` with `inboxCursor`, call `repo.list`, and return `{ items, nextCursor }` where `nextCursor` is null when fewer than `limit` rows came back. Items are serialised as `{ id, title, body, deepLink, createdAt, readAt }`.

5. **Unread count.** `GET /unread-count` calls `repo.unreadCount(req.userId)`, which runs `SELECT count(*) FROM notifications WHERE user_id = $1 AND read_at IS NULL`, and returns `{ unread }`.

6. **Mark read.** `POST /:id/read` calls `repo.markRead(id)`, which runs `UPDATE notifications SET read_at = COALESCE(read_at, now()) WHERE id = $1`. `COALESCE` keeps the first timestamp, and an already-read row still matches, so repeat calls return `204`. If `rowCount` is 0 we respond with `notFound("notification")`.

7. **Mark all read.** `POST /read-all` calls `repo.markAllRead(req.userId)`, which runs `UPDATE notifications SET read_at = now() WHERE user_id = $1 AND read_at IS NULL`, then responds `204`. The partial index from step 1 locates exactly the rows to update.

8. **Validation.** Reject a non-UUID `:id` with `badRequest` before querying, so malformed IDs never hit the database.

9. **Wiring.** Mount the router in `src/app.ts`: `app.use("/v1/notifications", requireUser, notificationsRouter)`. Errors propagate to the existing `errorHandler`, giving the standard envelope.

10. **API docs.** Add the four endpoints to `docs/mobile-api.md`, including the cursor semantics and the limit cap.

## Test strategy

- `test/notifications.test.ts` (new, supertest with `db/pool` mocked, as in `activity.test.ts`):
  - list returns items in the expected shape with a `nextCursor`, and `limit=200` is capped;
  - unread-count returns the repo value;
  - mark read returns 204 when a row is updated, 204 on a repeat call, and 404 when no row matches;
  - read-all returns 204 and passes the caller's id to the repo;
  - unauthenticated requests get 401 on every route.
- `test/inboxCursor.test.ts` (new): cursor round trip, invalid cursor rejected, limit defaults and cap.
- Index usage for `unread-count` will be checked with `EXPLAIN ANALYZE` against a production snapshot in staging before release; we are looking for an index-only scan on the partial index.

## Rollout and notes

- Run the migration first; `CONCURRENTLY` avoids locking the table, but on 30M rows each index takes several minutes, so it goes in its own deploy.
- The endpoints ship dark; the apps enable the inbox screen behind the `inbox_v1` remote flag in 6.3.
- We will add a Grafana panel for `unread-count` latency, since it runs on every foreground, and alert if p95 crosses 40 ms.
- The response shape for items uses camelCase, which the mobile model layer already decodes; `readAt` is `null` for unread items.
- No changes to the producing services are needed; they already write `read_at = NULL` on insert.
- `docs/mobile-api.md` is the only documentation change; the Postman collection is generated from it.
