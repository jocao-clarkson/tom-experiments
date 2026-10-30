import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class JobConfig:
    drop_dir: Path
    archive_dir: Path
    reports_dir: Path
    db_path: Path
    upsert_chunk_size: int = 5000
    extra: dict = field(default_factory=dict)


def load(job_name: str, path: str | None = None) -> JobConfig:
    """Load [jobs.<job_name>] from merch-batch.toml, with [defaults] underneath."""
    cfg_path = Path(path or os.environ.get("MERCH_BATCH_CONFIG", "merch-batch.toml"))
    with cfg_path.open("rb") as f:
        raw = tomllib.load(f)
    merged = {**raw.get("defaults", {}), **raw.get("jobs", {}).get(job_name, {})}
    known = {"drop_dir", "archive_dir", "reports_dir", "db_path", "upsert_chunk_size"}
    return JobConfig(
        drop_dir=Path(merged["drop_dir"]),
        archive_dir=Path(merged["archive_dir"]),
        reports_dir=Path(merged["reports_dir"]),
        db_path=Path(merged["db_path"]),
        upsert_chunk_size=int(merged.get("upsert_chunk_size", 5000)),
        extra={k: v for k, v in merged.items() if k not in known},
    )
