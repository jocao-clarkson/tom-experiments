# Spec: `deployer rollback`

**Team:** Release Engineering
**Consumers:** on-call engineers (interactive), CI pipelines (non-interactive)

## Goal

Rolling back today means looking up the previous release id in the dashboard and redeploying it by hand, which is slow during an incident. Add a `rollback` command that does the right thing by default, is safe in production, and can be scripted from CI.

## Functional requirements

- **R1.** `deployer rollback <service> [--to <release-id>] [--env <env>]`, where `--env` defaults to `staging`. Without `--to`, the target is the most recent **successful** release in that environment before the current one, taken from `GET /services/:svc/releases?env=<env>&status=succeeded` (newest first).
- **R2.** In `production`, the command asks for interactive confirmation unless `--yes` is given. If stdin is not interactive and `--yes` is missing, it does not prompt; it fails with `confirmation required; re-run with --yes` and exit code 3. A declined prompt also exits 3.
- **R3.** Start the rollback with `POST /services/:svc/rollbacks` `{ env, releaseId }`, which returns `202 { id, fromRelease, toRelease }`. Then poll `GET /rollbacks/:id` every 5 seconds until `status` is `succeeded` or `failed`, for at most 10 minutes in total.
- **R4.** With `--json`, print one line to stdout: `{ rollbackId, service, env, fromRelease, toRelease, status }`.
- **R5.** Exit codes:
  - 0: rollback succeeded;
  - 1: rollback failed, or the API returned an error;
  - 2: usage error;
  - 3: aborted, or confirmation required;
  - 4: timed out waiting. The message must say that the rollback may still be in progress and print its id.
- **R6.** A global `--token <token>` option overrides the configured token for that invocation, for CI systems that cannot set per-step environment variables.

## Acceptance criteria

- **AC1.** With releases `r3` (current), `r2` (failed) and `r1` (succeeded), `rollback web` targets `r1`.
- **AC2.** `rollback web --env production` in a non-TTY without `--yes` exits 3 without calling the rollbacks API.
- **AC3.** A rollback still `in_progress` after 10 minutes exits 4 and prints the rollback id.
- **AC4.** `--json` output parses as JSON and contains every R4 field.
- **AC5.** `deployer --token abc rollback web --yes` authenticates with `abc` even when `DEPLOYER_TOKEN` is set.
- **AC6.** A transient network error while polling does not end the command, as long as the 10-minute limit has not been reached.

## Non-functional constraints

- No new runtime dependencies; Node 18 or later.
- Tokens must never be printed, including with `--verbose`.
- The unit test suite must stay under 60 seconds in CI.
- Behaviour should match `deploy` wherever this spec doesn't say otherwise.

## Out of scope

- Rolling back database migrations.
- Multi-service or dependency-aware rollbacks.
- Changes to the `deploy` command's behaviour.
