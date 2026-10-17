# Plan: Profile avatar upload

## Overview

A new `putAvatar` handler in `internal/api/avatar.go` reads the image, validates it, renders two square JPEGs with `media.SquareJPEG`, stores them through `storage.BlobStore`, and moves the user to the new version with `users.Repo.SetAvatarVersion`. Signed URLs come from `BlobStore.SignedURL` with a 1-hour TTL.

## Steps

1. **Route** (`internal/api/server.go`). Register `PUT /v1/me/avatar` as `chain(http.HandlerFunc(s.putAvatar), RequireUser(s.Tokens))`. `LimitBody` is left out on this route because `DefaultBodyLimit` (64 KB) would reject every image. The handler enforces the 5 MB limit itself (step 3).

2. **Read the upload** (`internal/api/avatar.go`). If the request `Content-Type` starts with `multipart/form-data`, call `r.ParseMultipartForm(5 << 20)` and open the `file` part. Otherwise use `r.Body` directly. Either way, read the image with `io.ReadAll` into a `[]byte`, because decoding and re-encoding both need the bytes.

3. **Size check** (`internal/api/avatar.go`). Reject with `413 body_too_large` when the request's `ContentLength` or the bytes read exceed `5 << 20`. Applying the same 5 MB rule to the whole request body in both modes keeps one simple, predictable limit for clients (R3).

4. **Type sniffing** (`internal/api/avatar.go`). `http.DetectContentType(data[:512])` must return `image/jpeg` or `image/png`, otherwise `415 unsupported_media_type`. Headers and filenames are never consulted (R2, AC3).

5. **Decode** (`internal/api/avatar.go`). `image.Decode(bytes.NewReader(data))`, with `image/jpeg` and `image/png` registered. A decode error returns `415`.

6. **Render** (`internal/api/avatar.go`). `media.SquareJPEG(img, 512, 85)` and `media.SquareJPEG(img, 128, 80)`.

7. **Version and keys** (`internal/api/avatar.go`). Load the user, set `next := u.AvatarVersion + 1`, and use keys `avatars/{id}/v{next}/512.jpg` and `.../128.jpg` (R4).

8. **Replace previous version** (`internal/api/avatar.go`). If `u.AvatarVersion > 0`, call `Blobs.DeletePrefix(ctx, "avatars/{id}/v{old}/")` first, so that a user never has more than one set of objects in storage. Then `Put` both new renditions.

9. **Commit version** (`internal/api/avatar.go`). `Users.SetAvatarVersion(ctx, id, u.AvatarVersion, next)`. On `users.ErrConflict`, return `409 conflict` and delete the just-written `v{next}` objects. Other errors return `500` (R5).

10. **Respond** (`internal/api/avatar.go`). Sign both keys with `SignedURL(ctx, key, time.Hour)` and return `200 {"avatar": {"large_url", "small_url"}}` (R5).

## Test strategy

- `internal/api/avatar_test.go`, using `httptest`, `storage.NewFake()` and a stub token verifier. The user repo runs against a `sqlmock`-style fake `*sql.DB` wrapper defined in the test file.
  - A PNG raw upload returns 200, both renditions exist in the fake store under `v1/`, and the URLs carry `ttl=1h0m0s` (R4, R5).
  - A multipart upload of the same PNG returns 200 (R1).
  - An HTML body sent as `image/jpeg` gets 415, and a PNG sent as `image/gif` gets 200 (AC3).
  - A second upload deletes the `v1/` objects and writes `v2/` (R7).
  - A conflict from `SetAvatarVersion` returns 409 and leaves no `v{next}` objects.
- The existing `media` tests cover `SquareJPEG` dimensions, so no new media tests are needed.

## Rollout and notes

- Deploy order: backend first, then the app release that shows the upload button. The new route is unreachable from older app versions, so there is nothing to migrate and nothing to backfill.
- Dashboards: add a panel for `PUT /v1/me/avatar` latency and status codes (413, 415, 409 broken out) to the existing profile service dashboard. We'll watch it for the first week.
- The app feature flag `avatar_upload` stays off until the backend is deployed in every region.
- `ParseMultipartForm` uses temporary files for parts above its memory threshold, which is fine on our pods' ephemeral disk.
- Encoding two JPEGs from a 5 MB source takes about 300 ms in local benchmarks, well inside the 2 s budget.
- Old avatars from before versioning do not exist, because initials are rendered client-side.
