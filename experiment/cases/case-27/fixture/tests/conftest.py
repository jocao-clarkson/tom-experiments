import gzip
import json
import sqlite3

import pytest

from etl.events import LocalStorage
from etl.warehouse import Warehouse


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path / "bucket")


@pytest.fixture
def write_events(tmp_path):
    def _write(day: str, events: list, name: str = "part-0", raw_lines: list[str] | None = None):
        d = tmp_path / "bucket" / "events" / f"dt={day}"
        d.mkdir(parents=True, exist_ok=True)
        with gzip.open(d / f"{name}.jsonl.gz", "wt", encoding="utf-8") as fh:
            for e in events:
                fh.write(json.dumps(e) + "\n")
            for line in raw_lines or []:
                fh.write(line + "\n")
    return _write


@pytest.fixture
def warehouse():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE sessions_daily (day TEXT, platform TEXT, sessions INT, users INT)")
    return Warehouse(conn, paramstyle="?")
