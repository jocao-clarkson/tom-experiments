# Spec: Service-account API key rotation and revocation

## Goal

Customers rotate service-account keys by creating a new key and deleting the old one, which breaks their integrations for however long the deploy takes. Add first-class rotation with a grace period, and an immediate revoke for leaked keys.

## Functional requirements

- **R1.** `POST /v1/service-accounts/{id}/keys/{keyId}/rotate`, requiring scope `keys:admin`. Optional body `{"grace_seconds": int}`, default 86400, allowed 0 to 604800; out of range returns 400 `invalid_grace`. Rotation creates a new key with the same scopes and sets the old key's `expires_at` to now plus the grace period.
- **R2.** Response 201: `{"key": {"id", "prefix", "plaintext", "scopes", "created_at"}, "previous": {"id", "expires_at"}}`. The plaintext is shown only in this response.
- **R3.** Rotating a key that already has an `expires_at` (it is mid-rotation) returns 409 `rotation_in_progress`.
- **R4.** `POST /v1/service-accounts/{id}/keys/{keyId}/revoke`, requiring `keys:admin`, revokes the key immediately. Revoked keys, and old keys past their grace period, must be rejected by every API instance within 5 seconds.
- **R5.** Every rotation and revocation writes an audit event (`key.rotated`, `key.revoked`) with actor, account, and key ids. Key changes must never go unaudited: if the audit write fails, the operation fails and nothing changes.
- **R6.** Secrets (plaintext keys) never appear in audit events or logs.
- **R7.** `GET /v1/service-accounts/{id}/keys` shows `expires_at` for keys in their grace period (it already does).

## Acceptance criteria

- **AC1.** After rotation with `grace_seconds: 3600`, both keys authenticate; 3601 seconds later only the new key does.
- **AC2.** After revoke, the key is rejected on all instances within 5 seconds.
- **AC3.** If the audit write fails, rotate returns 500.
- **AC4.** `grace_seconds: 604801` returns 400 `invalid_grace`; a caller without `keys:admin` gets 403.
- **AC5.** Rotating the same key twice returns 409 the second time.
- **AC6.** A test asserts that no audit event contains the plaintext.

## Non-functional constraints

- Key verification runs on every API request (about 20k rps across 12 instances). It must not add a database round trip per request; p99 verification stays under 2 ms. Key lookups against the database stay under 1,000 queries per second fleet-wide (about 30,000 active keys; the same cluster serves billing).
- No new infrastructure (no Redis, no pub/sub).
- New keys use the existing key format and hashing.

## Out of scope

- Scheduled or automatic rotation.
- Emailing key owners.
- Changing scopes during rotation.
