"""Pipeline configuration. Values come from pipeline.yaml, overridable by env."""
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Config:
    source_root: Path
    warehouse_dsn: str
    state_dir: Path = Path("state")
    clean_table: str = "analytics.events_clean"
    quarantine_table: str = "analytics.events_quarantine"
    lookback_days: int = 3
    extra: dict = field(default_factory=dict)

    @property
    def checkpoint_path(self) -> Path:
        return self.state_dir / "checkpoint.json"

    @property
    def history_path(self) -> Path:
        return self.state_dir / "history.jsonl"

    @property
    def lock_path(self) -> Path:
        return self.state_dir / "run.lock"


def load_config(path: str = "pipeline.yaml") -> Config:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    return Config(
        source_root=Path(os.environ.get("EVENTS_SOURCE_ROOT", raw["source_root"])),
        warehouse_dsn=os.environ.get("WAREHOUSE_DSN", raw["warehouse_dsn"]),
        state_dir=Path(raw.get("state_dir", "state")),
        lookback_days=int(raw.get("lookback_days", 3)),
        extra=raw.get("extra", {}),
    )
