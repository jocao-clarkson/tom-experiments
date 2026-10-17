import json
from datetime import date
from pathlib import Path

from pipeline.config import Config
from pipeline.runner import run


def _write_day(root: Path, day: str, events):
    d = root / f"dt={day}"
    d.mkdir(parents=True)
    (d / "part-0.jsonl").write_text("\n".join(json.dumps(e) for e in events))


def test_run_advances_checkpoint_and_is_rerunnable(tmp_path, warehouse):
    ev = {"event_id": "e1", "event_type": "click", "occurred_at": "2026-10-01T00:00:00Z", "user_id": 1}
    _write_day(tmp_path / "src", "2026-10-01", [ev])
    cfg = Config(source_root=tmp_path / "src", warehouse_dsn="", state_dir=tmp_path / "state")
    run(cfg, warehouse, date(2026, 10, 2))
    run(cfg, warehouse, date(2026, 10, 2), partitions=["2026-10-01"])
    assert len(warehouse.rows(cfg.clean_table)) == 1
    assert json.loads(cfg.checkpoint_path.read_text())["last_partition"] == "2026-10-01"
