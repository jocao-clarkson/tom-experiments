# Spec: Batch sync for offline workouts

**Squad:** Pacer Core · **Clients:** iOS and Android 7.0

## Goal

Runners often record workouts with no signal (trails, gyms, flights) and the app currently uploads them one by one when it reconnects, which is slow and fails partway on flaky networks. App 7.0 will send everything in one batch call and pull back changes made on the user's other devices in the same round trip.

## Functional requirements

- **R1.** `POST /v2/workouts/sync` accepts `{ "since": <cursor or null>, "workouts": [WorkoutIn, ...] }` with at most **200** workouts; more returns `413`. `WorkoutIn` is the existing model.
- **R2.** Each workout is matched by `(user, client_id)`. Outcomes per item: `created` (new), `updated` (applied over a stored copy), `duplicate` (identical to the stored copy), or `stale` (older than the stored copy, not applied).
- **R3.** Conflicts are resolved **last-write-wins on `client_updated_at`**. If the incoming and stored timestamps are equal and the content differs, the **incoming** copy wins.
- **R4.** The response is `200` with `{ "results": [ { "client_id", "status", "id" } ], "changes": [...], "next_cursor" }`. One bad item (validation failure) is reported as `status: "rejected"` with a message and does not fail the batch.
- **R5.** The endpoint honours `Idempotency-Key`: a retried request with the same key returns the original response.
- **R6.** `changes` contains workouts changed on the server since `since` (by any device, including deletions), up to 500, with `next_cursor` to continue. `since: null` means a full first sync.
- **R7.** When a sync creates or updates at least one workout, the user's **other** devices get one silent push (`reason: "workouts_changed"`) so they sync too. The calling device is identified by `X-Device-Id`.

## Acceptance criteria

- **AC1.** Sending the same batch twice with different idempotency keys yields `duplicate` for every item the second time.
- **AC2.** A stored workout with `client_updated_at` 10:05 is not overwritten by an incoming copy stamped 10:00 (`stale`).
- **AC3.** Equal timestamps with different content result in `updated`.
- **AC4.** A batch of 201 workouts returns 413.
- **AC5.** After a sync that changes data, other devices receive exactly one silent push; the calling device receives none.

## Non-functional constraints

- p95 latency under 1.5 s for a 200-item batch. The push gateway's p99 is around 3 s and it has had multi-minute outages.
- Clients on bad networks retry aggressively, often after the server has already committed.
- Device clocks are not trustworthy: support sees phones whose clocks are hours or days off.
- No new infrastructure.

## Out of scope

- Merging conflicting edits field by field.
- Sync for routes, gear, or social data.
- Web client.
