# Plan: `POST /v2/workouts/sync`

## Overview

The sync endpoint lives next to the existing workout routes in `app/api/workouts.py` and delegates to a new `SyncService` in `app/services/sync.py`. Per-item reconciliation uses `WorkoutRepo`, idempotency reuses `app/core/idempotency.py` exactly as `create_workout` does, and the whole batch is committed once. Other devices are notified through a lightweight async notifier so the push gateway never sits on the request path.

## Steps

1. **Request model.** In `app/api/workouts.py`, add `SyncRequest { since: str | None, workouts: list[dict] }`. Items are kept as raw dicts at this level and validated one by one in the service, so a single bad item becomes `rejected` instead of failing the whole request (R4). A list longer than 200 returns `413` before any work is done.

2. **Idempotency.** At the top of the handler, call `idempotency.replay_or_none(session, user.id, key)` and return the stored response if present. After processing, `idempotency.remember(...)` with the full response body, inside the same transaction as the workout writes.

3. **Item validation.** `SyncService.sync(user_id, items)` validates each item with `WorkoutIn.model_validate`; on `ValidationError` it records `{client_id, status: "rejected", message}` and moves on.

4. **Reconciliation.** For each valid item, `repo.get_by_client_id`:
   - no stored row: `repo.insert`, status `created`;
   - stored row with identical content: `duplicate`;
   - incoming `client_updated_at` later than stored: `repo.update`, status `updated`;
   - otherwise (older, or equal timestamps): keep the stored copy and report `stale`. Treating ties as stale avoids flip-flopping between two devices that sync at the same moment.

5. **Query cost.** 200 sequential `get_by_client_id` lookups would be slow, so add `WorkoutRepo.get_many_by_client_ids(user_id, client_ids)` using `client_id = ANY(:ids)` and look items up from that dict. Writes stay per item.

6. **Response.** Return `200` with `{ "results": [...] }`. Pulling server-side changes back to the client (`changes`, `next_cursor`) is left for a follow-up; for 7.0 the app will call the existing `GET /v2/workouts` after a sync to refresh, which keeps this endpoint focused on uploads.

7. **Device notification.** Add `app/services/sync_notifier.py` with a module-level `httpx.AsyncClient` (timeout 5 s) and `notify_other_devices(user_id, device_id)`, which posts the silent push to `settings.push_gateway_url`. After reconciliation, if any item was `created` or `updated`, the handler calls `asyncio.create_task(notify_other_devices(...))` before committing, so the push overlaps with the commit and adds no latency. Failures are logged by the task.

8. **Commit.** `await session.commit()` once after all items and the idempotency record are written. Any database error rolls back the whole batch and returns 500; clients retry with the same key.

9. **Metrics.** Count per-status outcomes with the existing request metrics middleware labels so we can watch the `stale` and `rejected` rates after launch.

## Test strategy

- `tests/test_sync_service.py` (new): reconciliation table tests against a fake repo covering `created`, `duplicate` (AC1), `stale` for an older copy (AC2), `updated` for a newer copy, and `rejected` for an invalid item alongside valid ones.
- `tests/test_sync_api.py` (new): idempotent replay returns the identical body for a repeated key; the handler calls the notifier when something changed and not when everything was a duplicate (notifier monkeypatched).
- A load test in staging with 200-item batches to confirm the 1.5 s p95.

## Rollout and notes

- Ship the endpoint before the 7.0 app release; older apps keep using `POST /v2/workouts`.
- Clock skew between devices is a known product limitation of last-write-wins, which the spec chose deliberately.
- Watch the gateway error logs from `sync_notifier` during the first week; if pushes fail often we can revisit.
