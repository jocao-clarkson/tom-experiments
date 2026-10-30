# Plan: Notification preferences and quiet hours

## Overview

A new `internal/prefs` package owns the preferences model, storage, HTTP handlers and the quiet-hours logic. `push.Sender` gains a preferences lookup before it fans out to devices. Preferences are stored as one row per user in a `notification_preferences` table.

## Steps

1. **Migration.** Add `migrations/0019_notification_preferences.sql`: `user_id text primary key`, `social`, `marketing` and `reminders` as `boolean not null`, nullable `qh_start`, `qh_end` and `qh_timezone` text columns, and `updated_at timestamptz not null default now()`.

2. **Model.** `internal/prefs/model.go` defines `Preferences`, `QuietHours`, `Defaults()` (all categories enabled, nil quiet hours) and `Enabled(category string) bool`. Categories are plain strings so `prefs` does not import `push`.

3. **Repository.** `internal/prefs/repo.go` adds a `Repo` interface (`Get`, `Put`) and a `SQLRepo`, following `devices.Repo`. `Get` returns `Defaults()` on `sql.ErrNoRows`. `Put` is a single `INSERT ... ON CONFLICT (user_id) DO UPDATE` that writes every column.

4. **Handlers.** `internal/prefs/handler.go` adds `GetHandler(r *CachedReader)` and `PutHandler(repo Repo, r *CachedReader)`. GET writes the document with `httpx.JSON`. PUT decodes through `http.MaxBytesReader(w, r.Body, 4096)` into a request struct with pointer fields, so a missing category is distinguishable from `false`, validates it, and saves the whole document.

5. **Validation and errors.** `validate(req)` checks that every field is present, `HH:MM` via `time.Parse("15:04", ...)`, `start != end`, and the timezone via `time.LoadLocation`. Failures go through a local `writePrefsError(w, code, field)` that writes the flat `{"code", "field"}` body with status 422, using the codes `invalid_preferences`, `invalid_time` and `bad_timezone`, with fields named after the Go struct (`QuietHours.TZ`, `Categories.Social`).

6. **Quiet-hours check.** `internal/prefs/quiet.go` adds `InQuietHours(q *QuietHours, now time.Time) bool`. It loads the user's location, converts `now` into it, and compares minutes since midnight: `startMin <= nowMin && nowMin < endMin`.

7. **Sender integration.** `push.Sender` gets a `Prefs` field (an interface with `Get(ctx, userID) (prefs.Preferences, error)`). `Send` calls `Prefs.Get` before `ListForUser`, so suppressed pushes never touch the devices table. If the lookup fails, `Send` logs the error and continues with `prefs.Defaults()`, so a database blip never blocks delivery. Then `security` skips the remaining checks; a disabled category increments `push_suppressed_total{reason="category"}` and returns nil; a push inside quiet hours increments `push_suppressed_total{reason="quiet_hours"}` and returns nil.

8. **Preference caching.** `internal/prefs/cache.go` adds `CachedReader`, which wraps a `Repo` with a `map[string]Preferences` behind a `sync.RWMutex`, filled on first read. Repeat sends to the same user skip the query, which keeps the sender inside the 5 ms budget. `PutHandler` calls `CachedReader.Invalidate(userID)` after a successful save so the new document is served at once.

9. **Wiring.** `cmd/api/main.go` builds `prefs.NewSQLRepo(db)` and a `CachedReader` over it, and registers `GET` and `PUT /v1/me/notification-preferences` behind the existing middleware chain. `cmd/worker/main.go` builds its own `CachedReader` over `prefs.NewSQLRepo(db)` and sets it as `Sender.Prefs`.

10. **Old clients.** No version gate is needed. Pre-5.2 clients never call the endpoints, and users without a row get `Defaults()` in the sender.

## Test strategy

- `internal/prefs/handler_test.go` with `httptest` and an in-memory `Repo` stub, in the style of `devices/handler_test.go`: GET defaults (AC1); PUT then GET round trip (AC2); `Mars/Olympus` returns 422 (AC4); a missing category and a non-boolean category both return `invalid_preferences`; a malformed `start` returns `invalid_time`.
- `internal/prefs/quiet_test.go`: table tests for `InQuietHours` with a 09:00–17:00 window at 08:59, 09:00, 16:59 and 17:00, in both UTC and Europe/Berlin.
- `internal/push/sender_test.go`: extend the existing test with a fake `Prefs`. Cases: a `security` push during quiet hours is delivered; a disabled `marketing` category is not delivered and increments `push_suppressed_total{reason="category"}` (checked with `metrics.Value`); a counting fake confirms one `Get` per `Send` (AC5).
- `internal/prefs/cache_test.go`: a second read is served without calling the repo, and `Invalidate` forces a fresh read.

## Rollout

- Deploy the migration, then the API, then the worker. The 5.2 app release follows once both are live.
- Users without a row behave exactly as today, so the worker can ship before anyone has saved preferences.
- Watch `push_suppressed_total` by reason for the first week; a rise in `category` suppressions is expected as users opt out of marketing.
