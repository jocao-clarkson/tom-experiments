# Plan: `deployctl rollback`

## Overview

A new `src/commands/rollback.ts` mirrors `deploy.ts`: resolve the target, confirm, start the rollback, and optionally wait. All HTTP goes through the shared `ApiClient`. `src/cli.ts` gains the subcommand and the `--to` and `--timeout` flags.

## Steps

1. **Flags.** In `src/cli.ts`, add `to` and `timeout` string options to `parseArgs`, and a `rollback` case that requires `<service>` (otherwise `UsageError`) and calls `rollback(api, out, { service, to, yes, wait, timeout, json, isTTY })`.

2. **Duration parsing.** Add a `parseDuration` helper at the bottom of `rollback.ts` that accepts `30s`, `10m`, or `1h` and returns milliseconds. An invalid value throws `UsageError`. When `--timeout` is not given, the wait uses `15m`.

3. **Target resolution.** Call `GET /services/:s/releases?status=succeeded&limit=2`. Index 0 is the current release. Without `--to`, the target is index 1; if there is none, throw `CliError("no previous successful release", 1)`. With `--to`, the target is the given value.

4. **Confirmation.** Unless `--yes` is set, print `web: r42 -> r41` to stderr and ask `Continue? [y/N]` with a `readline/promises` interface created in `rollback.ts`. An answer other than `y`/`yes` throws `AbortError()`. When `isTTY` is false, the command skips the prompt and throws `UsageError("refusing to roll back without confirmation in a non-interactive session; pass --yes")` before any write call.

5. **Start.** Call `api.request("POST", "/services/:s/rollbacks", { target_release })`. A 409 `ApiError` is rethrown as `CliError("a rollback is already in progress for <service>", 1)`. Other `ApiError`s propagate with exit 1, covering an unknown `--to` release. Non-GET requests are not retried by `ApiClient`, so the POST is sent once.

6. **Polling.** With `--wait`, call `GET /rollbacks/:id` every `POLL_MS = 1_000` until the state is `succeeded` or `failed`. An error from a poll propagates like any other `ApiError`. As in `deploy()`, the function takes an optional `sleep` argument so tests can run the loop without real delays.

7. **Human progress.** In human mode, each state change prints `  <state>` with `console.log`. When `isTTY` is true the line is green for `succeeded`, red for `failed`, and yellow otherwise, using ANSI codes.

8. **JSON events.** In `--json` mode, each state change is written with `out.result({ event: "state", state, at: new Date().toISOString() }, state)`, and completion writes `out.result({ event: "result", id, state }, ...)`. Without `--wait`, the command writes a single `out.result({ id, state }, "rollback <id> <state>")`.

9. **Deadline and exit codes.** The deadline is `Date.now()` plus the `--timeout` value, checked after each poll. Return 0 for `succeeded` and 1 for `failed`. When the deadline passes, throw `AbortError("timed out waiting for rollback <id>")`, which `cli.ts` reports on stderr.

10. **Help text.** Extend the usage string in `cli.ts` to list `rollback` and its flags.

11. **README.** Add a "Rolling back" section with an interactive example and a `--yes --wait --json` example for automation, and add exit code `3` to the exit-code list.

## Test strategy

New `test/rollback.test.ts`, using the `fakeFetch` and `capture` helpers from `test/deploy.test.ts` (moved to `test/helpers.ts`) and a no-op `sleep`:

- Default target: releases `[r42, r41]` produce a POST with `target_release: "r41"`.
- No previous release: exit 1 with the message.
- 409 on POST: exit 1 with the in-progress message (AC4).
- 404 on POST for `--to r0`: exit 1 (AC5).
- `--wait --json`: fake states `pending -> running -> succeeded`; check that stdout contains `state` events and ends with a `result` event whose state is `succeeded` (AC3).
- `--yes` goes straight to the POST without prompting.
- `parseDuration` accepts `30s`, `10m`, and `1h` and rejects `10x`.

Timeout behaviour (AC2) is checked against a staging service with a stuck rollback during the SRE game day. The `deploy` tests keep passing after the helper move.

## Rollout

- Release as 1.7.0 through the internal npm registry.
- Ask the SRE team to try it against the staging cluster during the next game day before it goes into the runbook.
- Update the incident runbook to use `deployctl rollback <service> --yes --wait` as step one.
