import json
import logging
import os
from contextlib import contextmanager
from datetime import date, timedelta

from pipeline import extract, transform
from pipeline.config import Config

log = logging.getLogger("pipeline.runner")


@contextmanager
def run_lock(cfg: Config):
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    fd = os.open(cfg.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode())
        yield
    finally:
        os.close(fd)
        os.remove(cfg.lock_path)


def read_checkpoint(cfg: Config) -> str | None:
    if not cfg.checkpoint_path.exists():
        return None
    return json.loads(cfg.checkpoint_path.read_text())["last_partition"]


def write_checkpoint(cfg: Config, partition: str) -> None:
    cfg.checkpoint_path.write_text(json.dumps({"last_partition": partition}))


def process_partition(cfg: Config, wh, partition: str) -> dict:
    clean, quarantined = transform.normalize(extract.read_partition(cfg.source_root, partition))
    loaded = wh.replace_partition(cfg.clean_table, partition, clean)
    held = wh.replace_partition(cfg.quarantine_table, partition, quarantined)
    return {"partition": partition, "loaded": loaded, "quarantined": held}


def pending_partitions(cfg: Config, today: date) -> list[str]:
    last = read_checkpoint(cfg)
    start = date.fromisoformat(last) + timedelta(days=1) if last else today - timedelta(days=cfg.lookback_days)
    days = (today - start).days
    return [(start + timedelta(days=i)).isoformat() for i in range(days)]


def run(cfg: Config, wh, today: date, partitions: list[str] | None = None) -> list[dict]:
    with run_lock(cfg):
        summaries = []
        for partition in partitions if partitions is not None else pending_partitions(cfg, today):
            summary = process_partition(cfg, wh, partition)
            write_checkpoint(cfg, partition)
            log.info("partition done %s", json.dumps(summary))
            summaries.append(summary)
        return summaries
