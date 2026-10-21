"""Run state kept on local disk: the run lock and the nightly checkpoint."""
import json
import os
from contextlib import contextmanager

from pipeline.config import Config


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


def record(cfg: Config, summary: dict) -> None:
    """Append the partition summary to the run history and move the checkpoint to it."""
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    with cfg.history_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary) + "\n")
    cfg.checkpoint_path.write_text(json.dumps({"last_partition": summary["partition"]}))
