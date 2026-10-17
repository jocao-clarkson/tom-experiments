# Plan: `deployctl rollback`

## Overview

A new `src/commands/rollback.ts` mirrors the structure of `deploy.ts`: resolve the target, confirm, start the rollback, and optionally wait. It uses `ApiClient` for all HTTP calls, so auth and GET retries come for free. `src/cli.ts` gains the subcommand and the `--to` and `--timeout` flags.

## Steps

1. **Flags.** In `src/cli.ts`, add `to` and `timeout` string options to `parseArgs`, and a `rollback` case that requires `<service>` (otherwise `UsageError`) and calls `rollback(api, out, {...})`.

2. **Duration parsing.** Add a small `parseDuration("30s" | "10m" | "1h")` helper at the bottom of `rollback.ts`; an invalid value throws `UsageError`. Default `10m`.

3. **Target resolution.** If `--to` is absent, `GET /services/:s/releases?status=succeeded&limit=2` and take index 1. If there is no such entry, throw `CliError("no previous successful release", 1)`. The current release is index 0 and is used for the confirmation text.

4. **Confirmation.** Prompt `web: r42 -> r41  Continue? [y/N]` with a short `readline` question written inline in `rollback.ts`, so the rollback prompt can show the release diff on its own line. When stdin is not a TTY and `--yes` is absent, skip the prompt and proceed: rollbacks are often triggered from incident automation, and blocking there would defeat the purpose of the command.

5. **Start.** `api.request("POST", "/services/:s/rollbacks", { target_release })`. A thrown `ApiError` with status 409 is rethrown as `CliError("a rollback is already in progress for <service>", 1)`; other `ApiError`s propagate unchanged (exit 1), which covers the unknown `--to` case. The POST keeps `ApiClient`'s default of no retry, because a retried create would start a second rollback.

6. **Waiting.** If `--wait`, poll `GET /rollbacks/:id` every 500 ms until `succeeded` or `failed`, or until the `--timeout` deadline. The short interval makes the command feel responsive during an incident, when every second counts.

7. **Progress output.** On each state change, print a progress line with `console.log`, coloured with ANSI codes (green for `succeeded`, red for `failed`, yellow otherwise).

8. **Result and exit code.** When the rollback finishes, call `out.result({ id, state }, "rollback <id> <state>")` and return 0 for `succeeded`, 1 for `failed`. On deadline expiry, throw `CliError("timed out waiting for rollback <id>", 1)`, consistent with how `deploy` gives up.

9. **Help text.** Extend the usage string in `cli.ts` to list `rollback` and its flags.

10. **README.** Add a "Rolling back" section with interactive and `--yes --wait --json` examples for automation.

## Test strategy

New `test/rollback.test.ts`, using the `fakeFetch` and `capture` helpers copied from `test/deploy.test.ts`:

- Default target: releases `[r42, r41]` results in a POST with `target_release: "r41"`.
- No previous release: exit 1 with the message.
- 409 on POST: exit 1 with the in-progress message (AC4).
- 404 on POST for `--to r0`: exit 1 (AC5).
- `--wait --json`: fake states `pending -> running -> succeeded`; parse stdout and check the final state.

Timeout behaviour (AC2) is easiest to verify by hand against a staging service with a stuck rollback, since a unit test would have to wait out the timeout.

## Rollout

- Release as 1.7.0 through the internal npm registry.
- Announce in the incident-response channel with the README link.
- Ask the SRE team to try it against the staging cluster during the next game day before it goes into the runbook.
- Update the incident runbook to use `deployctl rollback <service> --yes --wait` as step one.
