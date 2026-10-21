# Plan: Service-account API key rotation and revocation

## Overview

Add `Rotate` and `Revoke` handlers to `KeysAPI` in `internal/httpapi/keys.go`, routed behind `RequireScope("keys:admin")`. Rotation creates the replacement key and sets the old key's expiry in one transaction. Revocation marks the key and clears it from the verifier cache so it stops working right away. Each change writes an audit event.

## Steps

1. **Request parsing.** `Rotate` reads an optional `{"grace_hours": int}` body, default 24, max 168, and returns 400 `invalid_grace` outside that range. Hours are easier for customers to reason about than seconds and map directly onto the "1 day / 7 days" options in the console.

2. **Load and check.** Inside `Store.WithTx`, `GetKey(keyId)`, return 404 if it belongs to another account, and 409 `rotation_in_progress` if `ExpiresAt` is already set. A revoked key also returns 409, since rotating it would silently resurrect access the customer meant to cut off. All reads use the transaction's `tx`, not `a.Store`.

3. **New key material.** Generate the new secret with `crypto/rand` (32 bytes, hex) and hash it with `bcrypt` at cost 10 before storing it in `Hash`. Bcrypt is the stronger choice for long-lived credentials, and the cost is only paid at creation. `Prefix` is the first 8 characters of the hex secret.

4. **Persist.** `tx.CreateKey` for the new key with the old key's `Scopes`, then `tx.SetExpiry(oldID, now + grace)`. Commit.

5. **Response.** Return 201 with `key` (including `plaintext`) and `previous` (`id`, `expires_at`), reusing `keyResponse` for the new key.

6. **Revoke.** `Revoke` loads the key, checks the account, calls `Store.Revoke(id, now)`, and then evicts the key from the verifier cache so the next request with it fails.

7. **Cache access.** The verifier's cache is unexported, so export it as `Verifier.Cache` with a `Delete(hash)` method, and give `KeysAPI` a `Verifier *apikey.Verifier` field, set to the same verifier passed to `Routes`, so `Revoke` can call `a.Verifier.Cache.Delete(...)`.

8. **Audit events.** Once the change has committed, insert `key.rotated` or `key.revoked` into `audit_events` with `a.Store.(store.Execer).Exec(...)`. Metadata carries the account id, both key ids, and the rotate response payload for traceability.

9. **Error handling.** Unknown or foreign keys return 404, the checks in step 2 return 409, and store errors return 500 with the transaction rolled back. An audit insert error is logged at ERROR with the key id and also returns 500, so the caller knows to retry.

10. **Routing.** Register both routes in `httpapi.Routes` (`internal/httpapi/router.go`) behind `Authenticate` and `RequireScope("keys:admin")`, next to the existing create route.

11. **Docs.** Update the public API reference and the "Rotating keys" console help page.

## Test strategy

- `internal/httpapi/keys_test.go`, reusing the existing `fakeStore` and `clock.Fixed`:
  - Rotate returns 201 with both sections; the old key now has `expires_at = now + 24h`.
  - Rotating the same key again returns 409 (AC5).
  - `grace_hours: 169` returns 400; a key without `keys:admin` gets 403 when called through `Routes` (AC4).
  - Revoke followed by `Verifier.Verify` on the same verifier returns `ErrInvalid` (AC2).
- `internal/apikey/apikey_test.go`: add a case for `Cache.Delete`.
- AC1 is checked by advancing `clock.Fixed` past the grace period and calling `Verify` on the old key.

## Rollout

- No migration: `expires_at` and `revoked_at` already exist on `api_keys`.
- Ship the handlers first, then expose the "Rotate" button in the console.
- Add a dashboard panel counting `key.rotated` and `key.revoked` per day so support can confirm customer reports.
- Watch `unauthenticated` 401 rates per account after launch; a spike would point at customers cutting over before deploying the new key.
