# Plan: Image attachments on notes

## Overview

Add an `attachments` table and an `AttachmentsRepo`, two endpoints in `app/main.py`, and attachment data on the note JSON. Uploads go straight to S3 through the existing `Storage` wrapper; the API only records metadata and hands thumbnail work to the job queue.

## Steps

1. **Schema.** Extend `SCHEMA` in `app/db.py` with `attachments (id TEXT PRIMARY KEY, note_id TEXT NOT NULL, owner_id TEXT NOT NULL, key TEXT NOT NULL, content_type TEXT NOT NULL, size_bytes INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, completed_at TEXT)` and an index on `note_id`.

2. **Repository.** Add `AttachmentsRepo` in `app/db.py`, following the `NotesRepo` conventions: `create`, `get`, `mark_ready(attachment_id)` (sets `status` and `completed_at`, then commits), `list_for_note(note_id)`, and `count_ready(note_id)`.

3. **Create endpoint.** `POST /notes/{note_id}/attachments`: load the note with `get_note_for_owner` (404 if missing), check the type against the allowed set and `1 <= size_bytes <= MAX_UPLOAD_BYTES` (422 otherwise), then return 409 `attachment_limit` when `count_ready(note_id) >= 20`. Insert the row as `pending` with the key `attachments/{note_id}/{attachment_id}`.

4. **Presigned upload.** Call `app.state.storage.presign_upload(key, content_type, size_bytes)` and return its `url` and `fields` as `upload`, with status 201. The POST policy carries the `Content-Type` and `content-length-range` conditions, so S3 itself rejects an upload that does not match the declaration.

5. **Complete endpoint.** `POST /attachments/{attachment_id}/complete`: load the attachment with `AttachmentsRepo.get` (404 if missing). If its status is already `ready`, return the serialized attachment immediately. Otherwise call `app.state.storage.head(key)`, return 409 `upload_missing` when it is `None` and 409 `upload_mismatch` when the stored size or content type differs from the row, then call `mark_ready`.

6. **Thumbnail job.** After `mark_ready`, call `jobs.enqueue(conn, "thumbnail", {"attachment_id": ..., "key": ...}, dedupe_key=attachment_id)`. The dedupe key makes the enqueue idempotent, so a repeated or concurrent complete never puts a second thumbnail job on the queue. Respond 200 with the attachment in the same shape used inside note JSON, so the app can render it without refetching the note.

7. **Attachment shape.** Add `attachment_to_dict(row, storage)` to `app/serializers.py`, returning `id`, `content_type`, `status`, `download_url` from `Storage.download_url` (1 hour) for ready attachments, and `thumbnail_url` for `{key}.thumb.jpg`, the path the media worker writes to. Both URLs are `null` while the attachment is pending.

8. **Note JSON.** Extend `note_to_dict` in `app/serializers.py` to add `attachments`, loading rows with `AttachmentsRepo.list_for_note` and rendering each with `attachment_to_dict`. The serializer gets the repo and storage through a module-level `configure(repo, storage)`. Because `GET /notes/{id}` and `GET /sync` both build their responses with `note_to_dict`, both endpoints get attachments with no route changes.

9. **Wiring.** In `create_app`, construct `AttachmentsRepo` next to `NotesRepo`, expose it on `app.state`, and call `serializers.configure(app.state.attachments, app.state.storage)`.

10. **Docs.** Document both endpoints, the POST-policy upload flow, and the new error codes (`attachment_limit`, `upload_missing`, `upload_mismatch`) for the mobile teams in the API reference.

## Test strategy

New `tests/test_attachments.py`, using the existing `client`, `note` and `s3` fixtures from `tests/conftest.py`:

- Create returns 201 with an upload URL and fields, and the policy recorded in `s3.presigned_posts` carries the declared type and size; 12 MB and `image/gif` return 422 (AC1).
- Complete before `s3.put(...)` returns 409 `upload_missing`; after `s3.put`, it returns 200 and one `jobs` row exists; a second complete still leaves exactly one row (AC3).
- An object stored with a different size returns 409 `upload_mismatch`.
- With 20 ready attachments, the next create returns 409.
- `GET /notes/{id}` includes `attachments` with a `download_url`.

The existing `tests/test_notes.py` cases keep passing unchanged, since notes without attachments serialize an empty list.

## Rollout

- The schema change is additive and applied at startup.
- Ship the API first; the 4.0 apps enable the attachment button behind a remote flag.
- Watch p95 latency for both endpoints and the `jobs` table depth for the first few days after the flag is enabled.
- Coordinate with the media team so the `thumbnail` job consumer is deployed before the flag is turned on.
