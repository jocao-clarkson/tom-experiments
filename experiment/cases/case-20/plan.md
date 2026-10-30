# Plan: `POST /v2/workouts/sync`

## Overview

The sync endpoint lives next to the existing workout routes in `app/api/workouts.py` and delegates to a new `SyncService` in `app/services/sync.py`. Per-item reconciliation and the change feed use `WorkoutRepo`, retried requests are answered from a stored sync receipt, and the whole batch is committed once. Other devices are notified through a small async notifier.

## Steps

1. **Request model.** In `app/api/workouts.py`, add `SyncRequest { since: str | None, workouts: list[dict] }`. Items are kept as raw dicts at this level and validated one by one in the service, so a single bad item becomes `rejected` instead of failing the whole request (R4). A list longer than 200 returns `413` before any work is done.

2. **Sync receipts.** Add `app/db/receipts.py` with `ReceiptRepo.get(user_id, key)` and `ReceiptRepo.put(user_id, key, since, results)` over a new `sync_receipts` table keyed by `(user_id, key)`. The handler reads the key with `idempotency.idempotency_key(request)` and checks for a receipt first. On a hit it returns the stored `results` and rebuilds `changes` and `next_cursor` from the stored `since` (step 6), so the device always gets a current page. The receipt is written in the same transaction as the workouts.

3. **Item validation.** `SyncService.sync(user_id, since, items)` validates each item with `WorkoutIn.model_validate`; on `ValidationError` it records `{client_id, status: "rejected", message}` and moves on.

4. **Reconciliation.** For each valid item, look up the stored row (step 5):
   - no stored row: `repo.insert`, status `created`;
   - stored row whose `WorkoutIn` fields all equal the incoming item: `duplicate`;
   - incoming `client_updated_at` later than stored: `repo.update`, status `updated`;
   - otherwise (older, or equal timestamps): keep the stored copy and report `stale`. Treating ties as stale avoids flip-flopping between two devices that sync at the same moment.

5. **Query cost.** 200 sequential `get_by_client_id` lookups would be slow, so add `WorkoutRepo.get_many_by_client_ids(user_id, client_ids)` using `client_id = ANY(:ids)` and look items up from the returned dict. Writes stay per item.

6. **Changes.** After the writes, `SyncService.changes(user_id, since)` calls `repo.changed_since(user_id, since_ts, limit=500)`, where `since_ts` is parsed from the cursor and `since: null` maps to the epoch. Rows with `deleted = true` are left out of `changes`, since the client only needs workouts it can show. `next_cursor` is the ISO-8601 `server_updated_at` of the last row returned, or the incoming cursor when nothing changed.

7. **Response.** Return `200` with `{ "results", "changes", "next_cursor" }`. Each result carries `client_id`, `status`, `id` (null for `rejected` and `stale`), and `message` for `rejected`.

8. **Device notification.** Add `app/services/sync_notifier.py` with a module-level `httpx.AsyncClient` (timeout 5 s) and `notify_other_devices(user_id, device_id)`, which posts the silent push (`reason: "workouts_changed"`, excluding `device_id`) to `settings.push_gateway_url` with the gateway token. If any item was `created` or `updated`, the handler starts `asyncio.create_task(notify_other_devices(user.id, x_device_id))` and then proceeds to the commit. Failures are logged inside the task.

9. **Commit.** `await session.commit()` once after all items and the receipt are written. Any database error rolls back the whole batch and returns 500; clients retry with the same key.

10. **Routing.** The route joins the existing `router`, so `app/main.py` is unchanged.

## Test strategy

- `tests/test_sync_service.py` (new): reconciliation table tests against a fake repo covering `created`, `duplicate` (AC1), `stale` for an older copy (AC2), `updated` for a newer copy, and `rejected` for an invalid item alongside valid ones.
- `tests/test_sync_api.py` (new): a repeated key returns the stored results; a `changes` page stops at 500 rows and its `next_cursor` fetches the rest; the notifier is called when something changed and not when every item was a duplicate (notifier monkeypatched).
- A load test in staging with 200-item batches to confirm the 1.5 s p95.

## Rollout and notes

- Ship the endpoint before the 7.0 app release; older apps keep using `POST /v2/workouts`.
- The `sync_receipts` table is created in the same deploy, before the route is enabled.
- Watch the gateway error logs from `sync_notifier` during the first week, along with the share of `stale` and `rejected` results.
