# Spec: Image attachments on notes

## Goal

The most requested feature in app reviews is adding photos to notes. Let the mobile apps attach images to a note. Uploads go straight to object storage, and thumbnails are produced by the media team's existing worker.

## Functional requirements

- **R1.** `POST /notes/{note_id}/attachments` with `{"content_type", "size_bytes"}`. Only the note's owner may call it (404 otherwise). Allowed types are `image/jpeg`, `image/png`, and `image/heic`, up to 10 MB; anything else returns 422. It creates an attachment with status `pending` and returns `{"attachment_id", "upload": {"url", "fields"}}`, a presigned upload valid for 15 minutes that enforces the declared type and size at the storage layer.
- **R2.** `POST /attachments/{attachment_id}/complete`, owner only. Verify that the object exists in storage and that its stored size and type match the request. Mark it `ready` and enqueue a `thumbnail` job (`{"attachment_id", "key"}`). Completing an already-ready attachment returns the same 200 body and enqueues nothing.
- **R3.** A note may have at most 20 attachments, **counting uploads in progress**. The 21st returns 409 `attachment_limit`.
- **R4.** `GET /notes/{id}` and `GET /sync` include `"attachments": [{"id", "content_type", "status", "download_url", "thumbnail_url"}]` for each note. Download URLs expire after 1 hour.
- **R5.** Clients older than 4.0 must not receive the `attachments` key at all. Older Android builds fail on unknown keys.

## Acceptance criteria

- **AC1.** A 12 MB request, or `image/gif`, returns 422.
- **AC2.** Complete on another user's attachment returns 404.
- **AC3.** Complete before the object exists returns 409 `upload_missing`; a second complete on a ready attachment enqueues no second job.
- **AC4.** With 20 attachments (any mix of pending and ready), the next request returns 409.
- **AC5.** A 3.9 client gets no `attachments` key from either endpoint; a 4.0 client does.
- **AC6.** A user whose app was killed mid-upload can still add attachments to that note later in the day once the abandoned upload has lapsed.

## Non-functional constraints

- No image decoding or processing in the API request path; p95 for `complete` under 300 ms.
- Silent push payloads for shared notes must stay under the 4 KB APNs limit.
- No new dependencies in the API service.

## Out of scope

- The thumbnail worker itself (owned by the media team).
- Deleting attachments.
- Cleaning up orphaned objects or stale rows: a bucket lifecycle rule already deletes un-completed uploads after 1 day, and this project adds no background jobs.
