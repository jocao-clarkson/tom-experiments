# Spec: In-app notification inbox

**Squad:** Engagement · **Clients:** iOS 6.3, Android 6.3

## Goal

Push notifications are easy to miss and disappear once dismissed. The mobile apps are adding an inbox screen that lists past notifications and shows an unread badge. This spec covers the backend endpoints the inbox needs. Notifications are already written to the `notifications` table by the campaign and trip services (`id`, `user_id`, `title`, `body`, `deep_link`, `created_at`, `read_at`).

## Functional requirements

- **R1.** `GET /v1/notifications` returns the caller's notifications, newest first, as `{ items, nextCursor }`. It accepts `limit` (default 20) and `cursor`. A `limit` above **50** is treated as 50; the inbox screen never needs more and older devices struggle with large payloads.
- **R2.** `POST /v1/notifications/:id/read` marks one notification as read and returns `204`. It is idempotent: marking an already-read notification read again also returns `204` and does not change the original `read_at`. A notification that does not exist or belongs to another user returns `404`.
- **R3.** `GET /v1/notifications/unread-count` returns `{ "count": n }`.
- **R4.** `POST /v1/notifications/read-all` marks all of the caller's unread notifications read and returns `204`.
- **R5.** All endpoints require an authenticated user and use the standard error envelope.

## Acceptance criteria

- **AC1.** Paging through the inbox while new notifications are being created never shows the same notification twice and never skips one.
- **AC2.** `limit=200` returns at most 50 items.
- **AC3.** Calling the read endpoint twice for the same notification returns 204 both times, and `read_at` keeps its first value.
- **AC4.** User B calling the read endpoint for user A's notification gets 404 and A's notification stays unread.
- **AC5.** After `read-all`, unread-count returns 0.

## Non-functional constraints

- The `notifications` table holds ~30M rows; heavy users have tens of thousands.
- `unread-count` is called on every app foreground and must stay under 50 ms at p95.
- Follow the existing list endpoint conventions so the mobile networking layer can reuse its paging code.

## Out of scope

- Deleting notifications or retention changes.
- Writing notifications (owned by the producing services).
- Badge counts inside push payloads.
- Web client support.
