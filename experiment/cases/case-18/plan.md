# Plan: Key rotation with grace period

## Overview

Rotation is a new `KeyService.rotate` method plus two routes in `src/routes/keys.ts`. The old key moves to a new `rotating` status with a `grace_ends_at` timestamp; the existing hourly expiry job is extended to move rotating keys to `expired`. A short-lived re-display of the new secret supports CLI users who lose the response.

## Steps

1. **Migration.** `migrations/014_key_rotation.sql`: add `rotating` to the `api_keys.status` check constraint; add `grace_ends_at TIMESTAMPTZ`, `replaced_by UUID REFERENCES api_keys(id)`, and `pending_secret TEXT` with `pending_secret_set_at TIMESTAMPTZ`.

2. **Repository.** In `src/keys/keyRepo.ts`, add `markRotating(id, graceEndsAt, replacedBy)`, `setPendingSecret(id, secret)`, `getPendingSecret(id)`, and extend `expireDue()` to also set `status = 'expired'` where `status = 'rotating' AND grace_ends_at < now()`, and to null out `pending_secret` older than 10 minutes.

3. **Grace parameter.** Add `src/lib/parseHours.ts` with `parseGraceHours(raw)`: a missing or non-numeric value returns 24, and anything above 168 is capped at 168 (negative values become 0). Keeping this separate from `validate.ts` makes the unit explicit at the call site.

4. **Authorization.** In the rotate route, load the key with `repo.byId` (404 if missing), then allow the call when `key.ownerId === actor.id || actor.role === "org_admin"`; otherwise respond `403`. The check sits inline in the route because rotation has its own error messages for the CLI.

5. **Rotate.** `KeyService.rotate(actor, key, graceHours)`:
   - if `key.status !== "active"`, throw a `ConflictError` (409);
   - create the replacement via the existing `create(actor, key.name, ttlDays)` path, carrying over the remaining TTL if the old key had one;
   - call `repo.markRotating(key.id, now + graceHours, newKey.id)`;
   - call `repo.setPendingSecret(newKey.id, plaintext)` so the secret can be shown again (R7);
   - emit `logger.audit("api_key.rotated", { oldKeyId, newKeyId, graceEndsAt, actorId })`.

6. **Verification.** In `KeyService.verify`, accept keys whose status is `active` or `rotating`. The hourly `expireDue` run then moves rotating keys to `expired` once their grace ends.

7. **Rotate route.** `POST /keys/:id/rotate` returns `201` with `{ id, prefix, secret, expiresAt, graceEndsAt }`.

8. **Secret re-display.** `GET /keys/:id/secret`: load the key, require `actor.id === key.ownerId`, read `pending_secret`, and return `{ secret }` while it is non-null; otherwise `404`. The hourly job clears it after 10 minutes.

9. **Error handling.** Add `ConflictError` (status 409) next to `ForbiddenError` in `keyService.ts`; the existing error middleware in `server.ts` maps `status` to the response.

## Test strategy

- `test/keyService.test.ts`: extend with rotate on an active key (replacement created, old key marked rotating), rotate on a rotating key (409), and `verify` accepting a rotating key.
- `test/parseHours.test.ts` (new): default, capping at 168, negative to 0, non-numeric to default.
- `test/keysRoute.test.ts` (new, supertest with a stubbed service): 201 response shape, 403 for a non-owner member, 404 for an unknown key, and the secret endpoint returning the pending secret.
- Expiry timing (AC1) is exercised by the existing hourly job, which we will observe in staging after rotating a test key with a 1-hour grace period.

## Rollout and notes

- The migration is additive and safe to run before the deploy.
- The dashboard team will surface `rotating` keys with their grace end once this ships; until then, the CLI is the only client calling rotate.
- AppSec review is scheduled for the PR; the audit event fields were agreed with them in advance.
- Docs: add rotate and the secret endpoint to the public API reference, with a note that the secret endpoint is a convenience for CLI flows.
