# Spec: `deployctl rollback`

**Team:** Developer Experience · **Consumers:** on-call engineers, CI pipelines

## Goal

Today a rollback means finding the last good version in the dashboard and re-running `deployctl deploy` with it. During incidents that is slow and error-prone. We want a first-class `rollback` command that picks a sensible target, confirms with the operator, and can wait for the rollback to finish so scripts can depend on it.

The platform API already supports this:
- `GET /services/{service}/releases?limit=N` returns releases newest first (`id`, `version`, `status`, `createdAt`).
- `GET /services/{service}/releases/{id}` returns one release.
- `POST /services/{service}/rollbacks` with `{ "targetRelease": "<id>" }` returns `{ "id", "status" }` and honours the `Idempotency-Key` header.
- `GET /services/{service}/rollbacks/{id}` returns `{ "id", "status" }` where status is `pending`, `running`, `succeeded` or `failed`.

## Functional requirements

- **R1.** `deployctl rollback <service>` targets the most recent `succeeded` release **older than the current release**. If none exists in the last 20 releases, exit with a usage error explaining that `--to` is required.
- **R2.** `--to <release-id>` targets a specific release. It must exist and have status `succeeded`, otherwise exit with a usage error.
- **R3.** Before starting, print the current and target versions and ask for confirmation. `--yes` skips the prompt. Without a terminal and without `--yes`, refuse rather than proceed.
- **R4.** `--wait` polls the rollback every 5 seconds until it reaches `succeeded` or `failed`, or until `--timeout` (default `10m`) elapses.
- **R5.** `--json` prints a single JSON object `{ service, rollbackId, from, to, status }`.
- **R6.** Exit codes: `0` success (or started, without `--wait`), `1` operator declined, `2` usage error, `3` rollback finished as `failed`, `4` API or network error, `5` timed out waiting.

## Acceptance criteria

- **AC1.** With releases `[v12 running/current, v11 failed, v10 succeeded]`, `rollback web --yes` targets v10.
- **AC2.** `rollback web --to <failed release>` exits 2 without calling the rollback endpoint.
- **AC3.** In a non-TTY without `--yes` the command exits 2 and nothing is posted.
- **AC4.** A network blip while starting the rollback does not create two rollbacks.
- **AC5.** `--wait` against a rollback that never finishes exits 5 after the timeout.

## Non-functional constraints

- No new runtime dependencies.
- Tests run under Vitest with no network access; the whole suite should stay under 30 seconds.

## Out of scope

- Rolling back multiple services at once.
- Cancelling an in-progress rollback.
- Changes to the platform API.
