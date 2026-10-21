# Spec: Service-account API keys

**Team:** Identity Platform
**Driver:** Integrations GA (customers need machine-to-machine access)

## Goal

Customers' CI systems and back-office scripts currently sign in with a human admin's credentials. Org admins need to be able to create scoped API keys for service accounts, revoke them quickly, and see when they were last used.

## Functional requirements

- **R1.** `POST /orgs/{org_id}/api-keys` with `{ "name": string, "scopes": [string] }`, callable only by org admins (human users), creates a key. The response includes the full secret **once**, in the form `sk_live_` followed by 32 base62 characters, along with `id`, `name`, `scopes`, `prefix` and `created_at`.
- **R2.** Only the key's `prefix` (the first 8 characters after `sk_live_`) and a hash of the secret are stored. The secret cannot be retrieved after creation.
- **R3.** A request with `Authorization: Bearer sk_live_...` is authenticated as a `service_account` principal for the key's org, carrying exactly the key's scopes. Existing user JWT authentication keeps working unchanged.
- **R4.** `DELETE /orgs/{org_id}/api-keys/{id}` revokes a key. Requests using a revoked key must be rejected **within 60 seconds** of revocation.
- **R5.** Each key has a `last_used_at` timestamp, updated at most once per minute per key. It is shown in `GET /orgs/{org_id}/api-keys`, which never returns secrets.
- **R6.** Creating and revoking keys write audit events `api_key.created` and `api_key.revoked`. The metadata of both events includes the key id, name, and scopes.

## Acceptance criteria

- **AC1.** The created secret authenticates immediately, and `GET /orgs/{org_id}/api-keys` shows the key without its secret.
- **AC2.** A key with scope `invoices:read` gets 403 on an endpoint requiring `invoices:write`.
- **AC3.** 61 seconds after revocation, the key gets 401 on every instance.
- **AC4.** No secret value appears in the database, the audit table, or the logs.
- **AC5.** 1,000 requests with the same key within a minute cause at most one `last_used_at` write.
- **AC6.** An unknown or malformed `sk_live_` token gets 401 without revealing which part was wrong.

## Non-functional constraints

- API key authentication adds at most 5 ms p95 at 2,000 requests/s per region (spread across 6 instances).
- Secrets must never be written to logs or audit metadata.
- The keys table must tolerate 2k rps of authentication without lock contention.

## Out of scope

- Scheduled key rotation and expiry policies.
- Per-key IP allowlists.
- Showing per-key request counts in the UI.
