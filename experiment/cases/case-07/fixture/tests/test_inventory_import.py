import pytest

from pipeline.config import JobConfig
from pipeline.db import Database
from pipeline.jobs import inventory_import


@pytest.fixture
def env(tmp_path):
    cfg = JobConfig(
        drop_dir=tmp_path / "drop",
        archive_dir=tmp_path / "archive",
        reports_dir=tmp_path / "reports",
        db_path=tmp_path / "t.db",
        upsert_chunk_size=2,
    )
    (cfg.drop_dir / "inventory").mkdir(parents=True)
    db = Database(cfg.db_path)
    db.conn.executescript(
        """
        CREATE TABLE products (sku TEXT PRIMARY KEY);
        CREATE TABLE inventory (warehouse TEXT, sku TEXT, qty INTEGER, as_of TEXT,
                                PRIMARY KEY (warehouse, sku));
        INSERT INTO products VALUES ('A1'), ('B2'), ('C3');
        """
    )
    return cfg, db


def drop(cfg, name, text):
    p = cfg.drop_dir / "inventory" / name
    p.write_text(text, encoding="utf-8")
    return p


def test_loads_valid_rows_and_reports_rejects(env):
    cfg, db = env
    drop(cfg, "inventory_east_20240501.csv", "sku,qty\nA1,5\nB2,-1\nZZ,3\nC3,7\n")
    [outcome] = inventory_import.run(cfg, db)
    assert (outcome.loaded, outcome.rejected) == (2, 2)
    qty = dict(db.conn.execute("SELECT sku, qty FROM inventory").fetchall())
    assert qty == {"A1": 5, "C3": 7}
    report = (cfg.reports_dir / "inventory" / "inventory_east_20240501.rejects.csv").read_text()
    assert "3,qty_negative" in report and "4,unknown_sku" in report
    assert (cfg.archive_dir / "inventory" / "inventory_east_20240501.csv").exists()


def test_rerun_is_idempotent(env):
    cfg, db = env
    drop(cfg, "inventory_east_20240501.csv", "sku,qty\nA1,5\n")
    inventory_import.run(cfg, db)
    drop(cfg, "inventory_east_20240501.csv", "sku,qty\nA1,5\n")
    inventory_import.run(cfg, db)
    assert db.conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0] == 1


def test_ignores_files_not_matching_pattern(env):
    cfg, db = env
    drop(cfg, "notes.txt", "hello")
    assert inventory_import.run(cfg, db) == []
