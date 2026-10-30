# Plan: Order status push notifications

## Overview

Device registration is two new routes over the existing `DeviceRepo`. Sending happens in a pg-boss `JobQueue` job, so the status endpoint only pays for an enqueue. The job loads the user's devices, sends to each through a small gateway sender, and cleans up invalid tokens.

## Steps

1. **Device routes** (`src/api/routes/devices.ts`, new). `POST /v1/devices` checks that `token` is a string of at most 512 characters, `platform` is `"ios"` or `"android"`, and `appVersion` is a string of at most 32 characters. Errors return 400 with the `invalid_request` shape the status route uses. It then calls `DeviceRepo.upsertByToken` with `req.user.id`. `DELETE /v1/devices/:token` calls `deleteByToken(token, req.user.id)` and returns 404 when the row count is 0, otherwise 204 (R2).

2. **Device cap** (`src/devices/deviceRepo.ts`). Add `evictBeyond(userId, max)`, which deletes all but the `max` most recent rows by `last_seen_at`. The POST route calls it right after the upsert with `max = 10` (R1).

3. **Wire routes** (`src/api/app.ts`). Add `devices: DeviceRepo` to `AppDeps` and mount `app.use("/v1", deps.requireUser, deviceRoutes(deps.devices))` next to the `/internal` mount.

4. **Job definition** (`src/jobs/orderPush.ts`, new). Define the job name `order-push` and the payload `{ orderId, userId, status }`. Build the push per R6: title and body come from a fixed map keyed by status, and `data = { orderId, status }`.

5. **Gateway sender** (`src/push/orderSender.ts`, new). `sendOrderPush(config, device, push)` posts `{ platform, token, payload }` to `${config.push.gatewayUrl}/v1/send` with the bearer API key and aborts after `config.http.timeoutMs`. It returns `"sent"`, `"invalid"` for 404 or 410, and `"failed"` for any other status or an aborted request.

6. **Job handler** (`src/jobs/orderPush.ts`). `handleOrderPush(payload)` loads `deviceRepo.listForUser(userId)` and calls `sendOrderPush` for each device in sequence. On `"invalid"` it calls `deviceRepo.deleteByToken(token)` (R4) and continues. On `"failed"` it logs the last six characters of the token with the HTTP status and moves on to the next device.

7. **Trigger** (`src/orders/orderService.ts`). In `updateStatus`, inside the transaction callback and right after the `UPDATE orders` statement, call `queue.enqueue("order-push", { orderId, userId, status: to }, { attempts: 1 })` when `to` is `shipped` or `delivered`. `OrderService` gets the `JobQueue` as a new constructor argument. This keeps the trigger next to the status write.

8. **Duplicate status events** (`src/jobs/orderPush.ts`). If the warehouse system posts the same status twice, `updateStatus` rejects the second call as an invalid transition (`shipped` to `shipped` is not allowed), so duplicates cannot reach the queue. The apps also collapse notifications with the same `orderId` and `status` on the device, which covers any remaining edge cases.

9. **Worker registration** (`src/worker.ts`, new; the `worker` npm script already points at its build output). Call `loadConfig()`, create the `pg` pool, `DeviceRepo` and `JobQueue`, and register `handleOrderPush` with `queue.register("order-push", ...)`, passing the config through to `sendOrderPush`.

## Test strategy

- `tests/devices.test.ts`: route tests with supertest and a fake `DeviceRepo`. Cover validation errors, upsert, delete of an owned token (204), delete of a foreign token (404), and that `evictBeyond` is called with 10.
- `tests/orderSender.test.ts`: stub global `fetch`; 200 gives `"sent"`, 410 and 404 give `"invalid"`, 500 gives `"failed"`.
- `tests/orderPush.test.ts`: unit tests for `handleOrderPush` with a fake sender:
  - three devices give three sends (AC1);
  - an `"invalid"` result deletes the device (AC4);
  - the push contains only `orderId` and `status` and the fixed copy (R6).
- `tests/orderService.test.ts`: extend the existing test to assert that `enqueue` is called for `shipped` and not for `packed`.
- AC6 is satisfied by design: the endpoint only enqueues.

## Rollout and notes

- Release the backend first. The apps' token registration is behind a feature flag, turned on after the backend has been live for a day.
- Set `PUSH_GATEWAY_URL` and `PUSH_API_KEY` on the worker deployment as well as the API.
- Watch the gateway error rate and `order-push` job durations in the pg-boss dashboard.
- Sending in sequence is fine for a 10-device cap; at a 5 s timeout the worst case is 50 s per job, well within pg-boss's default job expiry.
