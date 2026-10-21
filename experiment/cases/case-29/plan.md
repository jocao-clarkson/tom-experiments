# Plan: `deployctl rollback`

## Overview

A new `src/commands/rollback.ts` mirrors the structure of `deploy.ts`: resolve the target, confirm, start the rollback, and optionally wait. It uses `ApiClient` for all HTTP calls, so auth, timeouts, and GET retries come from the shared client. `src/cli.ts` gains the subcommand and the `--to` and `--timeout` flags.

## Steps

1. **Flags.** In `src/cli.ts`, add `to` and `timeout` string options to `parseArgs`, and a `rollback` case that requires `<service>` (otherwise `UsageError`) and calls `rollback(api, out, { service, to, yes, wait, timeout, json, isTTY })`.

2. **Duration parsing.** Add a `parseDuration` helper at the bottom of `rollback.ts` that accepts `30s`, `10m`, or `1h` and returns milliseconds. An invalid value throws `UsageError`. When `--timeout` is not given, the wait uses `15m`.

3. **Target resolution.** If `--to` is absent, call `GET /services/:s/releases?status=succeeded&limit=2` and take index 1. If there is no such entry, throw `CliError("no previous successful release", 1)`. Index 0 is the current release and is used for the confirmation text. With `--to`, the current release comes from the same call and the target is the given value.

4. **Confirmation.** Unless `--yes` is set, print `web: r42 -> r41` on its own line to stderr and ask `Continue? [y/N]` with a `readline/promises` question created in `rollback.ts`. An answer other than `y`/`yes` throws `AbortError()`. When stdin is not a TTY, the command does not prompt and throws `AbortError("refusing to roll back without confirmation in a non-interactive session; pass --yes")` before any write call.

5. **Start.** Call `api.request("POST", "/services/:s/rollbacks", { target_release })`. An `ApiError` with status 409 is rethrown as `CliError("a rollback is already in progress for <service>", 1)`. Other `ApiError`s propagate unchanged with exit 1, which covers an unknown `--to` release. The POST uses `ApiClient`'s default for non-GET requests, so it is sent once.

6. **Waiting.** If `--wait`, poll `GET /rollbacks/:id` with `POLL_MS = 1_000` until the state is `succeeded` or `failed`, or until `Date.now()` passes the deadline computed from `--timeout`. As in `deploy()`, the function takes an optional `sleep` argument so tests can run the loop without real delays.

7. **Human progress.** In human mode, each state change prints `  <state>` with `console.log`. When `isTTY` is true the line is green for `succeeded`, red for `failed`, and yellow otherwise, using ANSI codes.

8. **JSON events.** In `--json` mode, each state change is written with `out.result({ event: "state", state, at: new Date().toISOString() }, state)`, and completion writes `out.result({ event: "result", id, state }, ...)`. Without `--wait`, the command writes a single `out.result({ id, state }, "rollback <id> <state>")`.

9. **Exit codes.** Return 0 for `succeeded` and 1 for `failed`. When the deadline passes, throw `AbortError("timed out waiting for rollback <id>")`, which `cli.ts` already reports on stderr before exiting.

10. **Help text.** Extend the usage string in `cli.ts` to list `rollback` and its flags.

11. **README.** Add a "Rolling back" section with an interactive example and a `--yes --wait --json` example for automation, and add exit code `3` to the exit-code list.

## Test strategy

New `test/rollback.test.ts`, using the `fakeFetch` and `capture` helpers from `test/deploy.test.ts` (moved to `test/helpers.ts` so both files import them) and a no-op `sleep`:

- Default target: releases `[r42, r41]` produce a POST with `target_release: "r41"`.
- No previous release: exit 1 with the message.
- 409 on POST: exit 1 with the in-progress message (AC4).
- 404 on POST for `--to r0`: exit 1 (AC5).
- `--wait --json`: fake states `pending -> running -> succeeded`; check that stdout contains `state` events and ends with a `result` event whose state is `succeeded` (AC3).
- `--yes` skips the prompt and goes straight to the POST.
- `parseDuration` accepts `30s`, `10m`, and `1h` and rejects `10x`.

Timeout behaviour (AC2) is checked against a staging service with a stuck rollback during the SRE game day below. The existing `deploy` tests run unchanged.

## Rollout

- Release as 1.7.0 through the internal npm registry.
- Announce in the incident-response channel with the README link.
- Ask the SRE team to try it against the staging cluster during the next game day before it goes into the runbook.
- Update the incident runbook to use `deployctl rollback <service> --yes --wait` as step one.
