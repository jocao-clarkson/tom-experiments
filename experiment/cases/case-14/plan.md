# Plan: `deployctl rollback`

## Overview

`rollback` is a new command module shaped like `deploy`: it takes the shared `ApiClient` and `OutputContext`, uses `confirm` for the prompt, and throws `CliError` subclasses, which `cli.ts` already maps to exit codes. Target selection and polling are plain functions so they can be tested without timers.

## Steps

1. **Exit codes.** In `src/errors.ts`, add `RollbackFailedError` (exit 3) and `WaitTimeoutError` (exit 5), both extending `CliError`. `UsageError` (2) and `ApiError` (4) already exist. "Operator declined" returns `1` directly, as `deploy` does today.

2. **Shared types.** Move the `Release` interface from `src/commands/status.ts` to a new `src/api/types.ts` and add `Rollback { id; status }`. Update the import in `status.ts`; no behaviour change.

3. **Target selection.** New `src/commands/rollback/target.ts` with `pickTarget(releases, toId?)`:
   - "current" is the newest release whose status is `running` or `succeeded`;
   - without `--to`, return the first `succeeded` release after the current one in the newest-first list, or throw `UsageError("no earlier successful release in the last 20; use --to")`;
   - with `--to`, the caller fetches that release with `GET /releases/{id}` (so targets older than 20 releases still work); a 404 or a non-`succeeded` status becomes a `UsageError`. A 404 arrives as `ApiError` with `status === 404`, which we convert so the exit code is 2.

4. **Duration parsing.** `src/commands/rollback/duration.ts`: `parseDuration("10m" | "90s" | "1h")` returning milliseconds, rejecting anything else with `UsageError`.

5. **Waiting.** `src/commands/rollback/wait.ts`: `waitForRollback(api, service, id, { intervalMs, timeoutMs, sleep, now })`. It loops on `GET /rollbacks/{id}`, returning on a terminal status and throwing `WaitTimeoutError` once `now() - start` reaches the timeout. `sleep` and `now` are injected. Polls go through `ApiClient.get`, so transient 5xx responses are retried; a persistent failure surfaces as `ApiError` (exit 4).

6. **Command.** `src/commands/rollback/index.ts` `rollbackCommand(api, out, args, flags)`:
   - fetch `releases?limit=20`, resolve the target (step 3);
   - print `current → target` and call `confirm(out, ..., flags.yes)`; a "no" returns 1. With `--json`, the summary and prompt go to stderr (we pass `{ ...out, stdout: process.stderr }` to `confirm`) so stdout stays a single JSON object;
   - generate one `randomUUID()` and call `api.post("/services/{s}/rollbacks", { body: { targetRelease }, idempotencyKey })`. Because the key is created once per invocation, the client's retries reuse it and the API deduplicates (AC4);
   - with `--wait`, call `waitForRollback`; a `failed` result throws `RollbackFailedError`;
   - print via `printResult` with `{ service, rollbackId, from, to, status }`, which already handles `--json`.

7. **CLI wiring.** In `src/cli.ts`, add `to`, `wait` and `timeout` options to `parseArgs` and a `rollback` case. `--timeout` without `--wait` is accepted but ignored; we print a one-line note in non-JSON mode.

8. **Help text and docs.** Update the usage string in `cli.ts`, `docs/commands.md` (including the exit code table) and `CHANGELOG.md`.

## Test strategy

All tests use Vitest with a stubbed `ApiClient` or an injected `fetchImpl`; nothing touches the network.

- `test/rollback/target.test.ts`: AC1 fixture list; no earlier success; current release is `succeeded` rather than `running`; `--to` pointing at a failed release (AC2) and at a 404.
- `test/rollback/wait.test.ts`: terminal `succeeded`, terminal `failed`, and a never-ending rollback with a fake `now`/`sleep` that crosses the timeout (AC5).
- `test/rollback/command.test.ts`: non-TTY without `--yes` rejects with `UsageError` and `post` is never called (AC3); declining returns 1; `--json` output shape.
- `test/client.test.ts`: add a case where a POST with an idempotency key gets a 503 then a 200, asserting both attempts sent the same `idempotency-key` header (AC4).
- `test/rollback/duration.test.ts`: accepted and rejected inputs.

## Rollout and notes

- Released as 1.10.0 through the usual npm publish job.
- The platform team confirmed idempotency keys are kept for 24 hours, which comfortably covers client retries.
- Open question for DX review: whether `rollback` without `--wait` should still print the dashboard URL for the rollback. Not required by the spec, so it is left out for now.
