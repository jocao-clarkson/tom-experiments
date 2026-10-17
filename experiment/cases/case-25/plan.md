# Plan: Notification preferences and quiet hours

## Overview

A new `internal/prefs` package owns the preferences model, the HTTP handlers, and the quiet-hours logic. `push.Sender` gains a preferences lookup before fanning out to devices. Preferences are stored as one row per user in a `notification_preferences` table with a JSONB `categories` column and nullable quiet-hours columns.

## Steps

1. **Migration.** Add `migrations/0019_notification_preferences.sql`: `user_id text primary key`, `categories jsonb not null`, `qh_start text`, `qh_end text`, `qh_timezone text`, `updated_at timestamptz`.

2. **Model.** `internal/prefs/model.go` defines `Preferences`, `QuietHours`, and `Defaults()` returning all categories enabled and nil quiet hours.

3. **GET handler.** `internal/prefs/handler.go` adds `GetHandler(db *sql.DB)`. It runs `SELECT categories, qh_start, qh_end, qh_timezone FROM notification_preferences WHERE user_id = $1` with `httpx.UserID(ctx)` and returns `Defaults()` on `sql.ErrNoRows`. Responses go through `httpx.JSON`.

4. **PUT handler.** `PutHandler(db *sql.DB)` decodes the body into `Preferences` with pointer fields, loads the current row, and overwrites only the fields present in the request before an `INSERT ... ON CONFLICT (user_id) DO UPDATE`. Clients can then send just the toggle that changed, which keeps settings-screen requests small.

5. **Validation and errors.** `validate(p)` checks `HH:MM` with `time.Parse("15:04", ...)`, `start != end`, and the timezone via `time.LoadLocation`. Errors are written by a local `writePrefsError(w, code, field)` that emits the flat `{"code", "field"}` body with status 422, using codes `invalid_preferences`, `invalid_time` and `bad_timezone`, with fields named after the Go struct (`QuietHours.TZ`, `Categories.Social`).

6. **Quiet-hours check.** `internal/prefs/quiet.go` adds `InQuietHours(q *QuietHours, now time.Time) bool`. It converts `now` into the user's location and compares minutes since midnight: `startMin <= nowMin && nowMin < endMin`.

7. **Sender integration.** `push.Sender` gets a `Prefs` field (an interface with `Get(ctx, userID) (Preferences, error)`). In `Send`, `security` bypasses the checks. For other categories, a disabled category is counted as `push_suppressed_total{reason="category"}` and returned early. Before the device fan-out, notifications inside quiet hours go to step 8.

8. **Deferred delivery.** Notifications that land inside quiet hours are appended to an in-process `deferred` slice keyed by user, and a goroutine started in `main.go` checks every minute and re-sends entries whose window has ended. Users wake up to their reminders instead of losing them. Each deferral also increments `push_suppressed_total{reason="quiet_hours"}`.

9. **Routing.** Register `GET` and `PUT /v1/me/notification-preferences` in `cmd/api/main.go` behind the existing middleware chain, and pass a prefs reader into the `Sender` in the worker.

10. **Old clients.** No version gate is needed. Pre-5.2 clients never call the endpoints, and users without a row get `Defaults()` in the sender.

## Test strategy

- `internal/prefs/handler_test.go` with `httptest` against the Postgres service the CI job already provides, applying migration 0019 in `TestMain` and truncating the table between tests: GET defaults (AC1); PUT then GET round-trip (AC2); `Mars/Olympus` returns 422 (AC4); a body with a non-boolean category returns `invalid_preferences`.
- `internal/prefs/quiet_test.go`: table tests for `InQuietHours` with a 09:00–17:00 window at 08:59, 09:00, and 17:00.
- `internal/push/sender_test.go`: extend the existing test with a `security` push during quiet hours and a disabled `marketing` category, checking the `push_suppressed_total` counter via `metrics.Value`.

## Rollout

- Deploy the migration and API first, then the worker. The 5.2 app release follows once both are live.
- The sender change is guarded by `PREFS_ENFORCED`, defaulting to off, so the worker can be deployed before any user has saved preferences and enabled once GET/PUT are verified in production.
- Monitor `push_suppressed_total` by reason for the first week; a spike in `category` suppressions is expected as users opt out of marketing.
