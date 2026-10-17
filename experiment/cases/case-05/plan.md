# Plan: Order status push notifications

## Overview

Device registration is a pair of new routes over the existing `DeviceRepo`. Sending happens in a background job on the pg-boss `JobQueue`, so the status update endpoint only pays for an enqueue. The job loads the user's devices, sends through `PushClient`, and cleans up invalid tokens.

## Steps

1. **Device routes** (`src/api/routes/devices.ts`, new). `POST /v1/devices` uses `validate({ token: { type: "string", maxLength: 512 }, platform: { type: "string", oneOf: ["ios", "android"] }, appVersion: { type: "string", maxLength: 32 } })` and calls `DeviceRepo.upsertByToken` with `req.user.id`. `DELETE /v1/devices/:token` calls `deleteByToken(token, req.user.id)` and returns 404 when the row count is 0 (R2).

2. **Device cap** (`src/devices/deviceRepo.ts`). Add `evictBeyond(userId, max)`, which deletes all but the `max` most recent rows by `last_seen_at`. The POST route calls it right after the upsert with `max = 10` (R1).

3. **Wire routes** (`src/api/app.ts`). Add `devices: DeviceRepo` to `AppDeps` and mount `deviceRoutes(deps.devices)` under `/v1` behind `deps.requireUser`.

4. **Job definition** (`src/jobs/orderPush.ts`, new). Define the job name `order-push` and the payload `{ orderId, userId, status }`. Build the payload per R6: title and body come from a fixed map keyed by status, and `data = { orderId, status }`.

5. **Job handler** (`src/jobs/orderPush.ts`). `handleOrderPush(payload)` loads `deviceRepo.listForUser(userId)` and calls `pushClient.send` for each device in sequence. If a result has `invalidToken: true`, it calls `deviceRepo.deleteByToken(token)` (R4) and continues. Other failures are logged with the status code and the loop moves on to the next device.

6. **Enqueue options** (`src/jobs/orderPush.ts`). Enqueue with `attempts: 1`. A pg-boss retry would re-run the handler, so a single attempt guarantees we never push twice for one status change.

7. **Trigger** (`src/orders/orderService.ts`). In `updateStatus`, inside the transaction callback and right after the `UPDATE orders` statement, call `queue.enqueue("order-push", { orderId, userId, status: to }, { attempts: 1 })` when `to` is `shipped` or `delivered`. `OrderService` gets the `JobQueue` as a new constructor argument. Putting the trigger next to the status write keeps the two together and easy to follow.

8. **Duplicate status events** (`src/jobs/orderPush.ts`). If the warehouse system posts the same status twice, `updateStatus` rejects the second call as an invalid transition (`shipped` to `shipped` is not allowed), so duplicates cannot reach the queue. The apps also collapse notifications with the same `orderId` and `status` on the device, which covers any remaining edge cases.

9. **Worker registration** (`src/worker.ts`, new; the `worker` npm script already points at its build output). Register `handleOrderPush` with `queue.register("order-push", ...)`, constructing `DeviceRepo` and `PushClient` from config.

## Test strategy

- `tests/devices.test.ts`: route tests with supertest and a fake `DeviceRepo`. Cover validation errors, upsert, delete of an owned token (204), delete of a foreign token (404), and that `evictBeyond` is called with 10.
- `tests/orderPush.test.ts`: unit tests for `handleOrderPush` with a fake `PushClient`:
  - three devices give three sends (AC1);
  - a 410 result deletes the device (AC4);
  - the payload contains only `orderId` and `status` and the fixed copy (R6).
- `tests/orderService.test.ts`: extend the existing test to assert that `enqueue` is called for `shipped` and not for `packed`.
- AC6 is satisfied by design: the endpoint only enqueues.

## Rollout and notes

- Release the backend first. The apps already register tokens with a feature flag, which will be turned on after the backend has been live for a day.
- Watch the gateway error rate and `order-push` job durations in the pg-boss dashboard.
- Sending in sequence is fine for a 10-device cap; at a 5 s timeout the worst case is 50 s per job, well within pg-boss's default job expiry.
- If gateway flakiness turns out to be common, we can revisit the attempt count.
