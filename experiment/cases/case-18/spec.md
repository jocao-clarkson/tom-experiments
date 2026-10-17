# Spec: API key rotation with a grace period

**Area:** Platform keys service · **Security owner:** AppSec

## Goal

Customers rotate API keys by creating a new key, redeploying, and deleting the old one. Anyone who forgets the last step leaves a live key behind, and anyone who deletes too early takes an outage. We want a single rotate action that issues a replacement key and keeps the old one working for a bounded grace period.

## Functional requirements

- **R1.** `POST /keys/:id/rotate` creates a replacement key with the same name, org, and owner, and returns it as `{ id, prefix, secret, expiresAt, graceEndsAt }`, with status `201`.
- **R2.** The old key keeps authenticating until `graceEndsAt`, then stops. During the grace period its status is `rotating`; afterwards `expired`.
- **R3.** The body may include `grace_period_hours`: an integer from **0 to 168**, default **24**. A missing value uses the default. Any other value (non-integer, negative, above 168) is rejected with `400` and no key is created.
- **R4.** Only the key's owner, or an `org_admin` of the key's org, may rotate it; others get `403`.
- **R5.** Rotating a key that is not `active` (for example one already `rotating`) returns `409`.
- **R6.** Write an audit event `api_key.rotated` with the old and new key IDs, `graceEndsAt`, and the acting user.
- **R7.** CLI users sometimes lose the rotate response. `GET /keys/:newId/secret` returns the new key's secret to the user who rotated it, **once**, and only within **10 minutes** of the rotation. After that, or after one successful retrieval, it returns `404`.

## Acceptance criteria

- **AC1.** After rotate with `grace_period_hours: 1`, both keys authenticate; 61 minutes later only the new one does.
- **AC2.** `grace_period_hours: 500` returns 400 and creates no key.
- **AC3.** A second rotate of the same key returns 409.
- **AC4.** The secret endpoint works once within 10 minutes and returns 404 on a second call, or on any call after 10 minutes.
- **AC5.** A member who is not the owner gets 403; so does an org admin of a different org.

## Non-functional constraints

- Plaintext secrets must never be written to the database or to logs unencrypted.
- An old key must stop authenticating within one minute of `graceEndsAt`.
- Concurrent rotate requests for the same key must not produce two replacement keys.

## Out of scope

- Automatic scheduled rotation.
- Rotating webhook signing secrets.
- Dashboard UI changes.
