# Plan: `deployer rollback`

## Overview

`rollback` is a new commander subcommand built like `deploy`: a `makeRollbackCommand(deps)` factory taking the same `Deps` (API client and streams), registered in `src/cli.ts`. The command resolves the target release, confirms when needed, starts the rollback, and polls until it reaches a terminal status. The output and exit handling reuse `src/lib/output.ts`.

## Steps

1. **Command skeleton** (`src/commands/rollback.ts`, new). `makeRollbackCommand(deps: () => Deps)` with `<service>`, `--to <release-id>`, `--env <env>` (default `staging`), `-y, --yes` and `--json`. Import the `Deps` type from `deploy.ts` so both commands share one shape.

2. **Resolve target** (`src/commands/rollback.ts`). If `--to` is given, use it. Otherwise call `api.get("/services/:svc/releases?env=...&status=succeeded")` and take the second entry. The first is the current release, so the second is the previous successful one (R1, AC1). If there is no second entry, print `no earlier successful release` and exit 1.

3. **Confirmation** (`src/commands/rollback.ts`). For `production` without `--yes`, prompt `Roll back <svc> in production to <release>? [y/N]` using a small `askYesNo()` helper built on `readline.createInterface({ input: process.stdin, output: process.stderr })`. The rollback prompt shows both release ids, which the shared helper's fixed question format does not fit well.

4. **Abort handling** (`src/commands/rollback.ts`). If the answer is not `y`/`yes`, call `handleAbort(d)` and set `process.exitCode` to its return value, exactly as `deploy` does, so that both commands behave the same when declined.

5. **Start rollback** (`src/commands/rollback.ts`). `api.post("/services/:svc/rollbacks", { env, releaseId })`. Since `ApiClient` never retries POST, there is no risk of starting two rollbacks.

6. **Polling** (`src/commands/rollback.ts`). Loop on `api.get("/rollbacks/:id")` with a 5-second `setTimeout` between calls until `status` is `succeeded` or `failed`. GETs already get the client's built-in retry for transient errors (AC6).

7. **Exit codes** (`src/lib/output.ts`). Add `TIMEOUT: 4` to `ExitCode` for the timeout path. Succeeded maps to `OK`, and failed or an `ApiError` maps to `FAILURE`.

8. **JSON output** (`src/commands/rollback.ts`). Use `printResult(d, json, { rollbackId, service, env, fromRelease, toRelease, status }, human)` (R4, AC4).

9. **Verbose diagnostics** (`src/commands/rollback.ts`). When `--verbose` is set, emit `debug(\`argv: ${process.argv.slice(2).join(" ")}\`)` and `debug(\`config: ${JSON.stringify(loadConfig())}\`)` at start-up, so that CI logs show exactly how the command was invoked and which API it is targeting.

10. **Token source** (`src/cli.ts`). No `--token` flag is added: `DEPLOYER_TOKEN` already has precedence over `~/.deployerrc` in `loadConfig`, and every CI system we support can set environment variables at the job level.

11. **Register** (`src/cli.ts`). `program.addCommand(makeRollbackCommand(deps))`.

## Test strategy

- `tests/rollback.test.ts`, in the style of `deploy.test.ts` with mocked `api` and captured streams:
  - target resolution: `--to` wins; otherwise the second succeeded release; no earlier release gives exit 1 (AC1);
  - `--yes` in production skips the prompt and calls `post`;
  - polling stops on `succeeded` (exit 0) and on `failed` (exit 1);
  - `--json` output parses and has all fields (AC4).
- Use `vi.useFakeTimers()` for the polling tests so that they don't wait the real 5 seconds.
- A declined prompt test stubs `askYesNo` through a module mock and asserts that `post` is never called.
- Human-readable output is checked with a snapshot of the success and failure messages, so wording changes are deliberate.

## Rollout and notes

- Released as 2.7.0. The changelog entry includes a short runbook snippet for on-call.
- `rollback` reuses the existing auth and config, so no new setup is needed for users.
- Server-side, the rollbacks endpoint already exists and is used by the dashboard.
- `deployer rollback --help` documents the default target selection and the exit codes, and the README's CI section gets an example invocation.
- We will dogfood the command in the staging pipeline for a week before announcing it.
