import gzip
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Iterator, Protocol


class Storage(Protocol):
    def list(self, prefix: str) -> list[str]: ...
    def open(self, key: str): ...


class LocalStorage:
    def __init__(self, root):
        from pathlib import Path
        self.root = Path(root)

    def list(self, prefix: str) -> list[str]:
        base = self.root / prefix
        if not base.exists():
            return []
        return sorted(str(p.relative_to(self.root)).replace("\\", "/") for p in base.rglob("*.jsonl.gz"))

    def open(self, key: str):
        return (self.root / key).open("rb")


class S3Storage:
    def __init__(self, bucket: str):
        import boto3
        self.bucket = bucket
        self.client = boto3.client("s3")

    def list(self, prefix: str) -> list[str]:
        keys = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(o["Key"] for o in page.get("Contents", []) if o["Key"].endswith(".jsonl.gz"))
        return sorted(keys)

    def open(self, key: str):
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"]


@dataclass
class ReadStats:
    lines: int = 0
    malformed: int = 0
    files: list[str] = field(default_factory=list)

    @property
    def malformed_ratio(self) -> float:
        return self.malformed / self.lines if self.lines else 0.0


def day_prefix(day: date) -> str:
    return f"events/dt={day.isoformat()}/"


def read_events(storage: Storage, day: date, stats: ReadStats) -> Iterator[dict]:
    """Stream events for one day partition. Lines that are not JSON objects
    are counted in stats.malformed and skipped."""
    for key in storage.list(day_prefix(day)):
        stats.files.append(key)
        with storage.open(key) as raw, gzip.open(raw, "rt", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                stats.lines += 1
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    stats.malformed += 1
                    continue
                if not isinstance(event, dict) or "event_id" not in event:
                    stats.malformed += 1
                    continue
                yield event
