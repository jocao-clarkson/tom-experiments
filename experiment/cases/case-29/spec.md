# Spec: `deployctl rollback`

## Goal

During incidents, engineers roll back by looking up the previous release in the web console and running `deployctl deploy` with it, which is slow and error-prone under pressure. Add a `rollback` command that does this in one step and can also be driven from automation.

## Functional requirements

- **R1.** `deployctl rollback <service> [--to <release>] [--yes] [--wait] [--timeout <duration>] [--json]`. `--timeout` accepts `s`, `m`, and `h` suffixes, defaults to `10m`, and only applies with `--wait`.
- **R2.** Without `--to`, the target is the previous successful release, the second entry of `GET /services/:s/releases?status=succeeded&limit=2`. If there is none, exit 1 with "no previous successful release".
- **R3.** Before starting, show `<service>: <current> -> <target>` and ask for confirmation unless `--yes` is given. In a non-interactive session without `--yes`, treat the invocation as a usage error and do not call any write endpoint. Automation must pass `--yes` explicitly.
- **R4.** Start the rollback with `POST /services/:s/rollbacks {"target_release"}`, which returns `{"id", "state"}`. The endpoint is not idempotent. A 409 `rollback_in_progress` exits 1 with "a rollback is already in progress for <service>".
- **R5.** With `--wait`, poll `GET /rollbacks/:id` until the state is `succeeded` or `failed`. Exit codes: 0 succeeded, 1 failed, 3 timed out.
- **R6.** `--json` without `--wait` prints one result object. With `--wait`, stdout is NDJSON: one `{"event": "state", "state", "at"}` line per state change, then a final `{"event": "result", "id", "state"}` line.
- **R7.** Human output shows a progress line per state change and uses colour only on a TTY, consistent with `deploy`.

## Acceptance criteria

- **AC1.** Non-TTY without `--yes`: exit 2, no POST made.
- **AC2.** `--wait --timeout 30s` against a rollback stuck in `running`: exit 3 after about 30 seconds.
- **AC3.** `--json --wait`: every stdout line parses as JSON on its own, there is one `state` line per transition, and the last line has `"event": "result"`.
- **AC4.** A 409 from the API: exit 1 with the in-progress message.
- **AC5.** `--to` an unknown release (404): exit 1.
- **AC6.** A 20-minute `--wait` stays within the API rate limit.

## Non-functional constraints

- API tokens are limited to 60 requests per minute, counted across every command run with that token. Engineers commonly run `deploy --wait` and `rollback --wait` side by side during an incident.
- No new dependencies.
- Tests run without network, using a fake `fetch`.
- The test suite currently runs in under 5 seconds; keep it that way.

## Out of scope

- Rolling back several services at once.
- Cancelling a running rollback.
- Changes to `deployctl deploy`.
