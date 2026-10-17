# Spec: Order status push notifications

**Squad:** Mobile Commerce
**Platforms:** iOS 6.12+, Android 6.12+

## Goal

Shoppers want to know when their order ships and when it arrives without having to open the app. The apps already obtain push tokens. The backend needs to store them and send a push when an order reaches `shipped` or `delivered`.

## Functional requirements

- **R1.** `POST /v1/devices` (authenticated user) registers `{ token, platform: "ios" | "android", appVersion }`. Registration is an upsert by token. A user can have at most 10 devices; registering an 11th evicts the device the user was least recently seen on.
- **R2.** `DELETE /v1/devices/:token` removes the caller's device. Deleting a token the caller does not own returns 404.
- **R3.** When an order's status changes to `shipped` or `delivered`, send a push to every device registered to the order's user.
- **R4.** Device tokens that the push gateway reports as invalid are deleted.
- **R5.** No push is sent to users whose `notifications.orderUpdates` preference is `false`.
- **R6.** The push `data` contains only `orderId` and `status`. Title and body are fixed per status ("Your order has shipped", "Your order was delivered") and contain no item names, addresses or other personal data.

## Acceptance criteria

- **AC1.** A status change to `shipped` produces exactly one push per registered device of the user.
- **AC2.** If the gateway times out for one of three devices, the other two still receive exactly one push each, and the failed device is retried.
- **AC3.** A status update that fails and is rolled back sends no push.
- **AC4.** A gateway response of 410 for a token removes that device.
- **AC5.** A user with `orderUpdates: false` receives nothing.
- **AC6.** The `POST /internal/orders/:id/status` latency does not depend on how many devices the user has or on gateway latency.

## Non-functional constraints

- Sending must not block the order status update request; p95 for that endpoint stays under 300 ms.
- Each device receives at most one push per status change. Duplicates generate support tickets and App Store complaints.
- Push gateway calls time out after 5 s. Retries must back off.
- Use the existing pg-boss job queue; no new infrastructure.

## Out of scope

- Marketing or promotional pushes.
- An in-app notification inbox.
- Quiet hours and per-device preferences.
