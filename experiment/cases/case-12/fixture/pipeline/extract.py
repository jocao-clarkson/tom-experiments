import json
from pathlib import Path
from typing import Iterator


def read_partition(source_root: Path, partition: str) -> Iterator[dict]:
    """Yield raw events for one day partition (dt=YYYY-MM-DD, the UTC day the collector received them)."""
    day_dir = source_root / f"dt={partition}"
    for path in sorted(day_dir.glob("*.jsonl")):
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)
