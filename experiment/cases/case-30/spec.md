# Spec: Image attachments on notes

## Goal

The most requested feature in app reviews is adding photos to notes. Let the mobile apps attach images to a note. Uploads go straight to object storage, and thumbnails are produced by the media team's existing worker.

## Functional requirements

- **R1.** `POST /notes/{note_id}/attachments` with `{"content_type", "size_bytes"}`. Only the note's owner may call it (404 otherwise). Allowed types are `image/jpeg`, `image/png`, and `image/heic`, up to 10 MB; anything else returns 422. It creates an attachment with status `pending` and returns 201 `{"attachment_id", "upload": {"url", "fields"}}`, a presigned upload that enforces the declared type and size at the storage layer.
- **R2.** `POST /attachments/{attachment_id}/complete`, owner only. Verify that the object exists in storage (409 `upload_missing` otherwise) and that its stored size and type match what was declared (409 `upload_mismatch` otherwise). Mark it `ready` and enqueue one `thumbnail` job (`{"attachment_id", "key"}`). Completing an already-ready attachment returns the same 200 body and enqueues nothing.
- **R3.** A note may have at most 20 attachments, **counting uploads in progress**. The 21st returns 409 `attachment_limit`.
- **R4.** `GET /notes/{id}` and `GET /sync` include `"attachments": [{"id", "content_type", "status", "download_url", "thumbnail_url"}]` for each note. Download URLs expire after 1 hour.
- **R5.** Clients older than 4.0 must not receive the `attachments` key at all. Older Android builds fail on unknown keys.

## Acceptance criteria

- **AC1.** A 12 MB request, or `image/gif`, returns 422.
- **AC2.** Complete on another user's attachment returns 404.
- **AC3.** Complete before the object exists returns 409 `upload_missing`; a second complete on a ready attachment enqueues no second job.
- **AC4.** With 20 attachments (any mix of pending and ready), the next request returns 409.
- **AC5.** A 3.9 client gets no `attachments` key from either endpoint; a 4.0 client does.

## Non-functional constraints

- No image decoding or processing in the API request path; p95 for `complete` under 300 ms.
- No new dependencies in the API service.

## Out of scope

- The thumbnail worker itself, owned by the media team. It reads `thumbnail` rows from the shared `jobs` table and deletes each row once the thumbnails are written.
- Deleting attachments.
- Removing orphaned objects from the bucket.
- Adding scheduled tasks or new workers to the API service.
