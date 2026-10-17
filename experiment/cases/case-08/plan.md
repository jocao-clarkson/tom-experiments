# Plan: Service-account API keys

## Overview

We add an `api_keys` table, CRUD routes under `/orgs/{org_id}/api-keys`, and a second branch in `current_principal` that recognises `sk_live_` bearer tokens and returns a `service_account` `Principal`. Because `Principal` already carries `kind` and `scopes`, existing scope checks (`require_scope`) work for keys without changes. Key lookups are cached in-process to stay inside the 5 ms budget.

## Steps

1. **Migration** (`migrations/0031_api_keys.sql`, new). `api_keys(id text pk, org_id text, name text, scopes text[], prefix char(8), key_hash char(64), created_by text, created_at timestamptz, revoked_at timestamptz, last_used_at timestamptz)`, with a unique index on `prefix` and an index on `org_id`.

2. **Key generation** (`authsvc/routes/api_keys.py`, new). `secret = "sk_live_" + random_base62(32)` using `security/tokens.py`, and `prefix = secret[8:16]`. Hash with `hashlib.sha256(secret.encode()).hexdigest()`, computed in a small `_key_hash()` helper at the top of the module. Argon2 would be far too slow on the request path, and these secrets have about 190 bits of entropy anyway.

3. **Create route** (`authsvc/routes/api_keys.py`). `POST /orgs/{org_id}/api-keys` depends on `current_principal` and calls `require_org_admin(org_id)`. It inserts the row and returns `{"id", "name", "scopes", "prefix", "created_at", "api_key": secret}` with 201 (R1, R2).

4. **Audit on create** (`authsvc/routes/api_keys.py`). In the same transaction, call `AuditLog(conn).record(actor=..., action="api_key.created", org_id=..., target=key_id, metadata={"key": response})`, so that the audit row mirrors exactly what the admin received. `scrub()` strips sensitive fields before persisting (R6).

5. **List and revoke** (`authsvc/routes/api_keys.py`). `GET` returns `id, name, scopes, prefix, created_at, last_used_at, revoked_at` and never the hash. `DELETE` sets `revoked_at = now()` and records `api_key.revoked` with id, name and scopes (R4, R5, R6).

6. **Rotation** (`authsvc/routes/api_keys.py`). `POST /orgs/{org_id}/api-keys/{id}/rotate` creates a new key with the same name and scopes and revokes the old one in a single transaction. Integrations asked for this as a convenience, and it is a few lines on top of steps 3 and 5.

7. **Authentication** (`authsvc/principal.py`). In `current_principal`, if the bearer value starts with `sk_live_`, call `_api_key_principal(value)` instead of decoding a JWT. It parses the prefix, loads the row by `prefix`, checks `row.key_hash == _key_hash(value)` and `revoked_at is None`, and returns `Principal(subject=row.id, org_id=row.org_id, kind="service_account", scopes=frozenset(row.scopes))`. Any failure raises the same `401 unauthenticated` (AC6). `_key_hash` is imported from `routes/api_keys.py`.

8. **Lookup cache** (`authsvc/principal.py`). Wrap the row lookup in a `TTLCache(maxsize=10_000, ttl=300)` keyed by prefix, so that steady-state authentication makes no DB round trip. Revocation clears the entry on the instance that served the `DELETE`.

9. **last_used_at** (`authsvc/principal.py`). After a successful key authentication, run `UPDATE api_keys SET last_used_at = now() WHERE id = %s` on the request's connection, so that the value is always fresh (R5).

10. **Wiring** (`authsvc/app.py`). Include the `api_keys` router.

## Test strategy

- `tests/test_api_keys.py` with FastAPI `TestClient` and a fake `db`:
  - an admin creates a key; the response has an `sk_live_` secret with 32 base62 characters, and the stored row holds only prefix and hash (R1, R2);
  - a non-admin user and a service account both get 403 on create;
  - the created secret authenticates and yields `kind="service_account"` with the right scopes (AC1);
  - an `invoices:read` key gets 403 on `require_scope("invoices:write")` (AC2);
  - a malformed token, an unknown prefix and a wrong suffix all give the same 401 body (AC6);
  - rotate returns a new secret and the old one stops working.
- The existing tests in `test_audit_and_principal.py` keep passing, which confirms user JWT auth is unchanged (R3).

## Rollout and notes

- Ship behind `API_KEYS_ENABLED`. Integrations GA is gated on this flag.
- Add `cachetools` to dependencies for `TTLCache`.
- The cache TTL can be tuned after launch once we see real hit rates.
