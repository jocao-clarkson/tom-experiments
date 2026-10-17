# Plan: Image attachments on notes

## Overview

Add an `attachments` table and an `AttachmentsRepo`, two endpoints in `app/main.py`, and attachment data on the note JSON. Uploads go straight to S3 with presigned URLs; the API only records metadata and hands work to the job queue.

## Steps

1. **Schema.** Extend `SCHEMA` in `app/db.py` with `attachments (id TEXT PRIMARY KEY, note_id TEXT, owner_id TEXT, key TEXT, content_type TEXT, size_bytes INTEGER, status TEXT, created_at TEXT, completed_at TEXT)` and an index on `note_id`.

2. **Repository.** Add `AttachmentsRepo` in `app/db.py` with `create`, `get`, `mark_ready`, `list_for_note`, and `count_ready(note_id)`.

3. **Create endpoint.** `POST /notes/{note_id}/attachments`: load the note with `get_note_for_owner` (404 if missing), validate type against the allowed set and `size_bytes <= 10 MB` (422 otherwise), then enforce the limit with `count_ready(note_id) >= 20` returning 409 `attachment_limit`. Counting only ready attachments means a failed or abandoned upload never blocks the user from trying again.

4. **Presigned upload.** In the handler, create a `boto3` S3 client and call `generate_presigned_url("put_object", Params={"Bucket", "Key", "ContentType"}, ExpiresIn=900)` for the key `attachments/{note_id}/{attachment_id}`. Return it as `upload.url` with empty `fields`. A presigned PUT is simpler for the iOS and Android upload code than a multipart POST.

5. **Complete endpoint.** `POST /attachments/{attachment_id}/complete` with `{"size_bytes"}`: load the attachment with `AttachmentsRepo.get`. If it is already `ready`, return it. Otherwise call `app.state.storage.head(key)` and return 409 `upload_missing` if absent. Compare the client-reported `size_bytes` with the value stored at creation (409 `size_mismatch` if they differ), then `mark_ready`, setting `completed_at`. The response body is the attachment in the same shape used inside note JSON, so the app can render it without refetching the note.

6. **Thumbnail.** Generate a 256 px JPEG preview inline with Pillow, upload it as `{key}.thumb.jpg`, and then enqueue the `thumbnail` job through `jobs.enqueue(conn, "thumbnail", {...}, dedupe_key=attachment_id)` so the media worker can produce the remaining sizes. Doing the first preview inline means the note shows an image immediately after upload.

7. **Serialization.** Extend `note_to_dict` in `app/serializers.py` to include `attachments`, built from `AttachmentsRepo.list_for_note` with `download_url` from `Storage.download_url` (1 hour) and `thumbnail_url` when present. Because `GET /notes/{id}` and `GET /sync` both use `note_to_dict`, both endpoints get attachments with no route changes.

8. **Dependencies.** Add `Pillow` to `pyproject.toml` for step 6.

9. **Wiring.** Construct `AttachmentsRepo` in `create_app` next to `NotesRepo` and expose it on `app.state`.

10. **Docs.** Document both endpoints and the upload flow for the mobile teams in the API reference.

## Test strategy

New `tests/test_attachments.py`, using the existing `client`, `note` and `s3` fixtures from `tests/conftest.py`:

- Create returns 201 with an upload URL; 12 MB and `image/gif` return 422 (AC1).
- Complete before `s3.put(...)` returns 409 `upload_missing`; after `s3.put`, it returns 200 and a `jobs` row exists; a second complete adds no job row (AC3).
- With 20 ready attachments, the next create returns 409.
- `GET /notes/{id}` includes `attachments` with a `download_url`.

## Rollout

- The schema change is additive and applied at startup.
- Ship the API first; the 4.0 apps enable the attachment button behind a remote flag.
- Watch p95 latency for both endpoints and the `jobs` table depth for the first few days after the flag is enabled.
- Coordinate with the media team so the `thumbnail` job consumer is deployed before the flag is turned on.
