import os
from dataclasses import dataclass

import boto3

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class StorageSettings:
    bucket: str = os.environ.get("NOTES_BUCKET", "notes-media")
    upload_expiry_s: int = 900
    download_expiry_s: int = 3600


class Storage:
    """Wraps S3. Uploads go directly from the app to S3 using presigned POST
    policies so the API never streams user files."""

    def __init__(self, settings: StorageSettings | None = None, client=None):
        self.settings = settings or StorageSettings()
        self.client = client or boto3.client("s3")

    def presign_upload(self, key: str, content_type: str, max_bytes: int) -> dict:
        return self.client.generate_presigned_post(
            Bucket=self.settings.bucket,
            Key=key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1, max_bytes],
            ],
            ExpiresIn=self.settings.upload_expiry_s,
        )

    def head(self, key: str) -> dict | None:
        try:
            r = self.client.head_object(Bucket=self.settings.bucket, Key=key)
        except self.client.exceptions.ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return None
            raise
        return {"size": r["ContentLength"], "content_type": r.get("ContentType")}

    def download_url(self, key: str) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.settings.bucket, "Key": key},
            ExpiresIn=self.settings.download_expiry_s,
        )
