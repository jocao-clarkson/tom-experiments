# Plan: Service-account API keys

## Overview

We add an `api_keys` table, admin routes under `/orgs/{org_id}/api-keys`, and a second branch in `current_principal` that recognises `sk_live_` bearer tokens and returns a `service_account` `Principal`. `Principal` already carries `kind` and `scopes`. Key rows are memoised in-process so steady-state authentication makes no DB round trip.

## Steps

1. **Migration** (`migrations/0031_api_keys.sql`, new). `api_keys(id text pk, org_id text not null, name text not null, scopes text[] not null, prefix char(8) not null, key_hash char(64) not null, created_by text not null, created_at timestamptz not null default now(), revoked_at timestamptz, last_used_at timestamptz)`, with a unique index on `prefix` and an index on `org_id`.

2. **Key generation and hashing** (`authsvc/routes/api_keys.py`, new). `secret = "sk_live_" + crypto.random_base62(32)` and `prefix = secret[8:16]`. A module-level `_key_hash(secret)` returns `hmac.new(settings.jwt_secret.encode(), secret.encode(), hashlib.sha256).hexdigest()`, stored in `key_hash`. On a prefix collision the insert is retried with a fresh secret, up to three times.

3. **Create route** (`authsvc/routes/api_keys.py`). `POST /orgs/{org_id}/api-keys` depends on `current_principal` and calls `principal.require_org_admin(org_id)`. It checks that `name` is non-empty and `scopes` is a non-empty list of strings, inserts the row, and returns 201 with `id`, `name`, `scopes`, `prefix`, `created_at` and the secret as `api_key` (R1, R2).

4. **Audit helper** (`authsvc/routes/api_keys.py`). `_write_audit(conn, principal, action, key_id, metadata)` inserts one `audit_events` row on the route's connection. Create calls it in the insert transaction with action `api_key.created` and metadata `{"api_key": {"id": key_id, "name": name, "scopes": scopes}}` (R6).

5. **List route** (`authsvc/routes/api_keys.py`). `GET /orgs/{org_id}/api-keys` (org admin) returns `id, name, scopes, prefix, created_at, last_used_at, revoked_at`, newest first. Neither the hash nor any secret is selected (R5).

6. **Revoke route** (`authsvc/routes/api_keys.py`). `DELETE /orgs/{org_id}/api-keys/{id}` (org admin) sets `revoked_at = now()` where `revoked_at is null`, calls `_write_audit` with `api_key.revoked` and metadata `{"api_key": {"id": key_id}}`, evicts the key's prefix from the lookup memo (step 8), and returns 204. Unknown ids and other orgs' ids return 404 (R4, R6).

7. **Authentication** (`authsvc/principal.py`). In `current_principal`, a bearer value starting with `sk_live_` goes to `_api_key_principal(value)` instead of `jwt.decode`. It checks for 40 characters with a base62 tail, loads the row by `value[8:16]`, verifies `hmac.compare_digest(row.key_hash, _key_hash(value))` with `_key_hash` imported from `routes/api_keys.py`, and requires `revoked_at is None` and `org_is_active(db, row.org_id)`. It returns `Principal(subject=row.id, org_id=row.org_id, kind="service_account", scopes=frozenset(row.scopes))`. Every failure raises the existing `401 unauthenticated` (R3, AC6).

8. **Lookup memo** (`authsvc/principal.py`). The row lookup goes through `_key_memo()`, an `lru_cache`d `TTLMemo(ttl=settings.cache_ttl_seconds, maxsize=10_000)` keyed by prefix, built like `_org_memo`. Revocation calls `_key_memo().evict(prefix)`.

9. **last_used_at** (`authsvc/principal.py`). After a successful key authentication, a FastAPI background task runs `UPDATE api_keys SET last_used_at = now() WHERE id = %s AND last_used_at < now() - interval '1 minute'`. Repeat writes within a minute become no-ops, across all instances (R5, AC5).

10. **Wiring** (`authsvc/app.py`, `authsvc/settings.py`). Include the `api_keys` router and add `api_keys_enabled` (`API_KEYS_ENABLED`, default off). When off, the router is not mounted and `sk_live_` tokens get 401.

## Test strategy

- `tests/test_api_keys.py`, using FastAPI `TestClient` with an in-memory fake `db`:
  - an admin creates a key; the response has `sk_live_` plus 32 base62 characters, and the stored row holds only prefix and hash (R1, R2);
  - a non-admin user and a service account get 403 on create, list and revoke;
  - the secret authenticates as `service_account` with the key's scopes and appears in `GET` without a secret (AC1);
  - an `invoices:read` key gets 403 on `require_scope("invoices:write")` (AC2);
  - malformed, unknown-prefix and wrong-tail tokens return identical 401 bodies (AC6);
  - revoke returns 204 and the next request with that key gets 401 (R4);
  - create and revoke each write one audit row with the right action, actor and target (R6).
- Existing tests in `tests/test_audit_and_principal.py` keep passing (R3).

## Rollout and notes

- Ship behind `API_KEYS_ENABLED`: staging first, then production when Integrations GA starts.
- Run one canary instance at `LOG_LEVEL=DEBUG` for the first day after enabling, to watch key authentication next to the JWT path.
- Dashboards: auth latency p95 by credential type, and the 401 rate on `sk_live_` tokens.
