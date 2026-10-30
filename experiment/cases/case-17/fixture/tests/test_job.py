import csv
from pathlib import Path

from etl.config import JobConfig
from etl.job import run
from etl.metrics import RecordingMetrics


def write_input(root: Path, day: str, rows):
    d = root / day
    d.mkdir(parents=True)
    with (d / "events.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["event_id", "visitor_id", "ts", "url", "user_agent", "ip"])
        w.writeheader()
        w.writerows(rows)


def test_run_writes_sessions_and_counts(tmp_path):
    rows = [
        {"event_id": "1", "visitor_id": "v", "ts": "2026-10-01T10:00:00", "url": "/", "user_agent": "Mozilla/5.0", "ip": "203.0.113.5"},
        {"event_id": "2", "visitor_id": "v", "ts": "2026-10-01T10:05:00", "url": "/a", "user_agent": "Mozilla/5.0", "ip": "203.0.113.5"},
    ]
    write_input(tmp_path / "in", "2026-10-01", rows)
    cfg = JobConfig(input_dir=tmp_path / "in", output_dir=tmp_path / "out")
    metrics = RecordingMetrics()
    summary = run(cfg, "2026-10-01", metrics)
    assert summary == {"day": "2026-10-01", "events": 2, "sessions": 1}
    assert (tmp_path / "out" / "sessions" / "dt=2026-10-01" / "part-0.csv").exists()
    assert metrics.flushed[("events.processed", ())] == 2
