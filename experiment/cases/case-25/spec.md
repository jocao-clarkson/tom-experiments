# Spec: Notification preferences and quiet hours

## Goal

App-store reviews keep mentioning late-night pushes. Let users choose which kinds of notifications they get and set a nightly quiet-hours window. The 5.2 app release ships the settings screen; the backend must be ready first.

## Functional requirements

- **R1.** `GET /v1/me/notification-preferences` returns `{"categories": {"social": bool, "marketing": bool, "reminders": bool}, "quiet_hours": {"start": "HH:MM", "end": "HH:MM", "timezone": "<IANA name>"} | null}`. Users with nothing saved get all categories `true` and `quiet_hours: null`.
- **R2.** `PUT` on the same path replaces the whole document. All three categories and `quiet_hours` (which may be `null`) are required.
- **R3.** Validation failures return 422 with body `{"code": "<code>", "field": "<json path>"}` so the settings screen can highlight the field. Codes: `invalid_preferences` (missing or wrong-typed field), `invalid_time` (not 24h `HH:MM`, or start equals end), `invalid_timezone` (not a known IANA zone). Example: `{"code": "invalid_timezone", "field": "quiet_hours.timezone"}`.
- **R4.** The push sender skips a notification when its category is disabled, or when the user's local time is inside quiet hours. Windows may cross midnight; `start` is inclusive and `end` exclusive. `security` notifications are always delivered and cannot be disabled.
- **R5.** Skipped notifications are dropped and counted in `push_suppressed_total` with label `reason` (`category` or `quiet_hours`).
- **R6.** Clients older than 5.2 have no settings screen. Their users keep receiving pushes under the defaults, and no existing endpoint changes behaviour.

## Acceptance criteria

- **AC1.** GET for a user with nothing saved returns the defaults.
- **AC2.** PUT followed by GET returns exactly the document that was PUT.
- **AC3.** With quiet hours 22:00–07:00 Europe/Berlin: a `social` push at 23:30 Berlin time is suppressed, one at 07:00 is delivered, and a `security` push at 23:30 is delivered.
- **AC4.** `"timezone": "Mars/Olympus"` returns 422 `{"code": "invalid_timezone", "field": "quiet_hours.timezone"}`.
- **AC5.** Preference checks add at most one database query per `Send` call.

## Non-functional constraints

- The API and push worker images stay on the existing distroless static build.
- Sender overhead p99 under 5 ms excluding the push gateway call.
- A saved document governs every push sent more than 60 seconds after the PUT returns.
- Marketing opt-out is the user's consent record: a marketing push must never reach a user whose saved preferences turn marketing off.
- No new external services.

## Out of scope

- Delivering suppressed notifications after quiet hours end.
- Per-device preferences.
- Email preferences.
