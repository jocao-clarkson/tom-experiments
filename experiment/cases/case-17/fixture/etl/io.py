import csv
from datetime import datetime
from pathlib import Path
from typing import Iterator

FIELDS = ("event_id", "visitor_id", "ts", "url", "user_agent", "ip")


def read_events(input_dir: Path, day: str) -> Iterator[dict]:
    """Stream events for one day from input_dir/<day>/*.csv without loading them all."""
    for path in sorted((input_dir / day).glob("*.csv")):
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                row["ts"] = datetime.fromisoformat(row["ts"])
                yield row
