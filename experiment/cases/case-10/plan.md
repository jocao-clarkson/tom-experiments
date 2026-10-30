# Plan: Profile avatar upload

## Overview

A new `putAvatar` handler in `internal/api/avatar.go` reads the image, checks its type, renders two square JPEGs with `media.SquareJPEG`, stores them through `storage.BlobStore`, and moves the user to the new version with `users.Repo.SetAvatarVersion`. Signed URLs come from `BlobStore.SignedURL` with a 1-hour TTL. No schema change is needed: `users.avatar_version` already exists and `Repo.Get` reads it.

## Steps

1. **Route** (`internal/api/server.go`). Register `PUT /v1/me/avatar` as `chain(http.HandlerFunc(s.putAvatar), RequireUser(s.Tokens))`. The route does not go through `authed`, whose `DefaultBodyLimit` (64 KB) is sized for JSON bodies; the handler enforces the upload limit itself (step 3).

2. **Read the upload** (`internal/api/avatar.go`). If the request `Content-Type` starts with `multipart/form-data`, call `r.ParseMultipartForm(5 << 20)` and open the `file` part. Otherwise use `r.Body`. In both cases read the image with `io.ReadAll` into a `[]byte`, since the type check and decoding both work from the bytes.

3. **Size check** (`internal/api/avatar.go`). Return `413 body_too_large` when `r.ContentLength` exceeds `5 << 20`, or when more than `5 << 20` bytes were read (R3).

4. **Type check** (`internal/api/avatar.go`). `http.DetectContentType(data[:512])` must return `image/jpeg` or `image/png`; anything else is `415 unsupported_media_type`. The request `Content-Type` and the part's filename are never consulted (R2, AC3).

5. **Decode** (`internal/api/avatar.go`). `image.Decode(bytes.NewReader(data))` with the `image/jpeg` and `image/png` decoders registered. A decode error returns `415`.

6. **Render** (`internal/api/avatar.go`). `media.SquareJPEG(img, 512, 85)` and `media.SquareJPEG(img, 128, 80)`.

7. **Version and keys** (`internal/api/avatar.go`). Load the user with `Users.Get`, set `next := u.AvatarVersion + 1`, and build `avatars/{id}/v{next}/512.jpg` and `avatars/{id}/v{next}/128.jpg` (R4).

8. **Replace previous version** (`internal/api/avatar.go`). If `u.AvatarVersion > 0`, call `Blobs.DeletePrefix(ctx, "avatars/{id}/v{old}/")`, then `Put` both new renditions with content type `image/jpeg`. Each user keeps exactly one set of objects in storage (R7).

9. **Commit version** (`internal/api/avatar.go`). `Users.SetAvatarVersion(ctx, id, u.AvatarVersion, next)`. On `users.ErrConflict`, delete the `v{next}` objects just written and return `409 conflict`. Other errors return `500` (R5).

10. **Respond** (`internal/api/avatar.go`). Sign both keys with `Blobs.SignedURL(ctx, key, time.Hour)` and return `200 {"avatar": {"large_url", "small_url"}}` (R5).

11. **Test dependency** (`go.mod`). Add `github.com/DATA-DOG/go-sqlmock` as a test-only requirement for the handler tests below.

## Test strategy

- `internal/api/avatar_test.go`, using `httptest`, `storage.NewFake()` and the `stubTokens` verifier from `profile_test.go`. The `users.Repo` is built on a `go-sqlmock` connection, so each test scripts the `SELECT` and the `UPDATE` result without a running database.
  - A raw PNG upload returns 200, both renditions are in the fake store under `v1/`, and the URLs carry `ttl=1h0m0s` (R4, R5).
  - The same PNG sent as multipart returns 200 (R1).
  - An HTML body sent as `image/jpeg` gets 415, and a PNG sent as `image/gif` gets 200 (AC3).
  - A second upload removes the `v1/` objects and writes `v2/` (R7).
  - An `UPDATE` that affects zero rows returns 409 and leaves no `v2/` objects behind (R5).
- `SquareJPEG` output dimensions are already covered in `internal/media/imageproc_test.go`, so no new media tests are needed.

## Rollout and notes

- Deploy order: backend first, then the app release that shows the upload button. Older app versions never call the new route, so there is nothing to migrate or backfill.
- Add a panel for `PUT /v1/me/avatar` latency and status codes (413, 415 and 409 broken out) to the profile service dashboard, and watch it for the first week.
- The app feature flag `avatar_upload` stays off until the backend is live in every region.
- `ParseMultipartForm` spills parts above its memory threshold to temporary files, which the pods' ephemeral disk handles.
- Encoding both JPEGs from a 5 MB source takes about 300 ms in local benchmarks, well inside the 2 s budget.
- No user has a stored avatar today (initials are drawn client-side), so everyone's first upload is `v1`.
