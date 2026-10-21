# Plan: Service-account API keys

## Overview

We add an `api_keys` table, admin routes under `/orgs/{org_id}/api-keys`, and a second branch in `current_principal` that recognises `sk_live_` bearer tokens and returns a `service_account` `Principal`. `Principal` already carries `kind` and `scopes`, so `require_scope` works for keys without changes. Key rows are cached in-process to keep authentication inside the 5 ms budget.

## Steps

1. **Migration** (`migrations/0031_api_keys.sql`, new). `api_keys(id text pk, org_id text not null, name text not null, scopes text[] not null, prefix char(8) not null, key_hash char(64) not null, created_by text not null, created_at timestamptz not null default now(), revoked_at timestamptz, last_used_at timestamptz)`, with a unique index on `prefix` and an index on `org_id`.

2. **Key generation and hashing** (`authsvc/routes/api_keys.py`, new). `secret = "sk_live_" + random_base62(32)` from `security/tokens.py`, and `prefix = secret[8:16]`. A module-level `_key_hash(secret)` returns `hmac.new(settings.jwt_secret.encode(), secret.encode(), hashlib.sha256).hexdigest()`, the 64-character value stored in `key_hash`. On a prefix collision the insert is retried with a fresh secret, up to three times.

3. **Create route** (`authsvc/routes/api_keys.py`). `POST /orgs/{org_id}/api-keys` depends on `current_principal` and calls `principal.require_org_admin(org_id)`. It checks that `name` is non-empty and `scopes` is a non-empty list of strings, inserts the row, and returns 201 with `id`, `name`, `scopes`, `prefix`, `created_at` and the secret as `api_key` (R1, R2).

4. **Audit on create** (`authsvc/routes/api_keys.py`). In the same transaction, `AuditLog(conn).record(actor=principal.subject, action="api_key.created", org_id=org_id, target=key_id, metadata={"api_key": {"id": key_id, "name": name, "scopes": scopes}})` (R6).

5. **List route** (`authsvc/routes/api_keys.py`). `GET /orgs/{org_id}/api-keys` (org admin) returns `id, name, scopes, prefix, created_at, last_used_at, revoked_at`, ordered by `created_at desc`. Neither the hash nor any secret is selected (R5).

6. **Revoke route** (`authsvc/routes/api_keys.py`). `DELETE /orgs/{org_id}/api-keys/{id}` (org admin) sets `revoked_at = now()` where `revoked_at is null`, records `api_key.revoked` with the same metadata shape as step 4, evicts the key's prefix from the lookup cache (step 8), and returns 204. Unknown ids and other orgs' ids return 404 (R4, R6).

7. **Authentication** (`authsvc/principal.py`). In `current_principal`, a bearer value starting with `sk_live_` goes to `_api_key_principal(value)` instead of `jwt.decode`. It checks that the value is 40 characters with a base62 tail, loads the row by `value[8:16]`, verifies `hmac.compare_digest(row.key_hash, _key_hash(value))` with `_key_hash` imported from `routes/api_keys.py`, and requires `revoked_at is None` and `orgs.is_active(db, row.org_id)`. It returns `Principal(subject=row.id, org_id=row.org_id, kind="service_account", scopes=frozenset(row.scopes))`. Every failure raises the existing `401 unauthenticated` (R3, AC6).

8. **Lookup cache** (`authsvc/principal.py`). The row lookup in step 7 goes through a module-level `cachetools.TTLCache(maxsize=10_000, ttl=settings.cache_ttl_seconds)` keyed by prefix, so steady-state authentication makes no DB round trip. Revocation calls `key_cache.pop(prefix, None)`.

9. **last_used_at** (`authsvc/principal.py`). After a successful key authentication, a FastAPI background task runs `UPDATE api_keys SET last_used_at = now() WHERE id = %s AND last_used_at < now() - interval '1 minute'`. The condition turns repeat writes within a minute into no-ops, so a hot key is written at most once per minute across all instances (R5, AC5).

10. **Wiring** (`authsvc/app.py`, `authsvc/settings.py`). Include the `api_keys` router and add an `api_keys_enabled` setting (`API_KEYS_ENABLED`, default off). When it is off, the router is not mounted and `sk_live_` tokens get 401.

## Test strategy

- `tests/test_api_keys.py`, using FastAPI `TestClient` with an in-memory fake `db`:
  - an admin creates a key; the response has `sk_live_` plus 32 base62 characters, and the stored row holds only prefix and hash (R1, R2);
  - a non-admin user and a service account get 403 on create, list and revoke;
  - the created secret authenticates as `kind="service_account"` with the key's scopes, and the key appears in `GET` without a secret (AC1);
  - an `invoices:read` key gets 403 on `require_scope("invoices:write")` (AC2);
  - a malformed token, an unknown prefix and a wrong tail all return identical 401 bodies (AC6);
  - revoke returns 204 and the next request with that key gets 401 (R4);
  - create and revoke each write one audit row with the right action, actor and target (R6).
- The existing tests in `tests/test_audit_and_principal.py` keep passing, which confirms user JWT auth is unchanged (R3).

## Rollout and notes

- Ship behind `API_KEYS_ENABLED`: staging first, then production when Integrations GA starts.
- Add `cachetools` to the `pyproject.toml` dependencies.
- Run one canary instance at `LOG_LEVEL=DEBUG` for the first day after enabling, to watch key authentication decisions next to the JWT path.
- Dashboards: auth latency p95 by credential type, and the 401 rate on `sk_live_` tokens.
