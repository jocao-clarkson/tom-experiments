# Plan: Key rotation with grace period

## Overview

Rotation is a new `KeyService.rotate` method plus two routes in `src/routes/keys.ts`. The old key moves to a new `rotating` status with a `grace_ends_at` timestamp, and the existing hourly expiry job is extended to move rotating keys to `expired`. The new secret is kept encrypted for a short re-display window so CLI users who lose the rotate response can fetch it again.

## Steps

1. **Migration.** `migrations/014_key_rotation.sql`: add `rotating` to the `api_keys.status` check constraint; add `grace_ends_at TIMESTAMPTZ`, `replaced_by UUID REFERENCES api_keys(id)`, `pending_secret TEXT` and `pending_secret_set_at TIMESTAMPTZ`.

2. **Repository.** In `src/keys/keyRepo.ts`, add `rotating` to `KeyStatus` and `graceEndsAt` to `ApiKey` and `COLS`. Add `claimForRotation(id, graceEndsAt)` (`UPDATE api_keys SET status = 'rotating', grace_ends_at = $2 WHERE id = $1 AND status = 'active' RETURNING id`), `setReplacedBy(id, newId)`, `setPendingSecret(id, sealed)` and `getPendingSecret(id)`. Extend `expireDue()` to set `status = 'expired'` where `status = 'rotating' AND grace_ends_at < now()`, and to null out `pending_secret` set more than 10 minutes ago.

3. **Grace parameter.** In the rotate route, read the value with the existing `intParam(req.body.grace_period_hours, { min: 0, max: 168, default: 24 })` from `src/lib/validate.ts`, the same helper `POST /keys` uses for `ttl_days`.

4. **Authorization.** In the rotate route, load the key with `repo.byId` (404 if missing), then allow the call when `key.ownerId === actor.id || actor.role === "org_admin"`; otherwise respond `403`. The check sits inline in the route because rotation has its own error messages for the CLI.

5. **Rotate.** `KeyService.rotate(actor, key, graceHours)`:
   - call `repo.claimForRotation(key.id, now + graceHours)`; if no row comes back, throw a `ConflictError` (409), so two concurrent requests cannot both proceed;
   - create the replacement through the existing `create(actor, key.name, ttlDays)` path, carrying over the remaining TTL if the old key had one;
   - call `repo.setReplacedBy(key.id, newKey.id)` and `repo.setPendingSecret(newKey.id, encrypt(plaintext))` using `src/lib/crypto.ts`;
   - emit `logger.audit("api_key.rotated", { oldKeyId, newKeyId, graceEndsAt, actorId })`;
   - call `this.cache.evict(key.id)` so the gateway's next lookup reads the `rotating` row. `KeyService` takes the `VerifyCache` as a second constructor argument, wired in `src/server.ts`.

6. **Verification.** In `KeyService.verify`, accept keys whose status is `active` or `rotating`. The hourly `expireDue` run then moves rotating keys to `expired` once their grace ends.

7. **Rotate route.** `POST /keys/:id/rotate` returns `201` with `{ id, prefix, secret, expiresAt, graceEndsAt }`.

8. **Secret re-display.** `GET /keys/:id/secret`: load the key, require `actor.id === key.ownerId`, read `pending_secret`, and return `{ secret: decrypt(pendingSecret) }` while it is non-null; otherwise `404`. The hourly job clears it after 10 minutes.

9. **Error handling.** Add `ConflictError` (status 409) next to `ForbiddenError` in `keyService.ts`; the existing error middleware in `server.ts` maps `status` to the response.

## Test strategy

- `test/keyService.test.ts`: extend with rotate on an active key (replacement created, old key claimed, pending secret stored encrypted), rotate when `claimForRotation` returns no row (409), `verify` accepting a rotating key, and `evict` called with the old key's id.
- `test/keysRoute.test.ts` (new, supertest with a stubbed service): 201 response shape, the default of 24 hours applied when `grace_period_hours` is omitted, 403 for a non-owner member, 404 for an unknown key, and the secret endpoint returning the decrypted pending secret.
- Expiry timing (AC1) is exercised by the existing hourly job, which we will observe in staging after rotating a test key with a 1-hour grace period.

## Rollout and notes

- The migration is additive and safe to run before the deploy.
- `KEYS_ENCRYPTION_KEY` is already set in every environment for webhook secrets, so no new configuration is needed.
- The dashboard team will surface `rotating` keys with their grace end once this ships; until then, the CLI is the only client calling rotate.
- AppSec review is scheduled for the PR; the audit event fields were agreed with them in advance.
- Docs: add rotate and the secret endpoint to the public API reference, with a note that the secret endpoint is a convenience for CLI flows.
