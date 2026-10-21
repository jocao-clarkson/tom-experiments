# Spec: Profile avatar upload

**Squad:** Fernway App, Profiles
**Clients:** iOS and Android 4.20+

## Goal

Profiles currently show initials only. Users should be able to upload a photo from the app and see it on their profile and next to their posts. The upload path must be safe to expose to every client, since anyone can send us arbitrary bytes.

## Functional requirements

- **R1.** `PUT /v1/me/avatar` accepts the image either as the raw request body or as `multipart/form-data` with a single `file` part. In both modes the image may be up to 5 MB (5,242,880 bytes).
- **R2.** The image type is determined by content sniffing. Client-supplied `Content-Type` headers and filenames are ignored. Only JPEG and PNG are accepted; anything else returns `415 unsupported_media_type`.
- **R3.** Images above **40 megapixels** return `422 image_too_large`. Images over 5 MB return `413 body_too_large`.
- **R4.** The server produces square JPEGs at 512×512 and 128×128 and stores them at `avatars/{userId}/v{version}/{size}.jpg`, where `version` increments with every successful upload.
- **R5.** The user's `avatar_version` is updated atomically. If two uploads race, one wins and the other gets `409 conflict`. The response is `200 { "avatar": { "large_url", "small_url" } }` with signed URLs valid for 1 hour.
- **R6.** `GET /v1/me` includes the same `avatar` object, or `null` when the user has no avatar.
- **R7.** Once the new version is in place, the previous version's objects are deleted.

## Acceptance criteria

- **AC1.** A JPEG of exactly 5,242,880 bytes is accepted, both as a raw body and as a multipart upload.
- **AC2.** A 5.1 MB upload gets 413, and the server never holds much more than 5 MB of a single request in memory.
- **AC3.** A PNG sent with `Content-Type: image/gif` is processed as a PNG. An HTML file sent as `image/jpeg` gets 415.
- **AC4.** An 8000×6000 PNG (48 MP) gets 422 `image_too_large`, without the server decoding the full pixel data.
- **AC5.** If the database update fails or conflicts, the user's existing avatar URLs keep working.
- **AC6.** After a successful upload, `GET /v1/me` returns the new avatar URLs.

## Non-functional constraints

- p95 under 2 s for a 5 MB upload, measured server-side.
- Memory per request must be bounded. The pods have 512 MB and serve about 40 concurrent requests.
- No new modules in `go.mod`. Image work uses the standard library and `golang.org/x/image`, which is already in use.
- Signed URLs are valid for exactly 1 hour.

## Out of scope

- Animated images (GIF, APNG, WebP).
- Client-side cropping UI; the server always center-crops.
- Moderation of uploaded images.
