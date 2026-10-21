from datetime import date, timedelta

from pipeline import extract, obs, state, transform
from pipeline.config import Config


def process_partition(cfg: Config, wh, partition: str) -> dict:
    clean, quarantined = transform.normalize(extract.read_partition(cfg.source_root, partition))
    loaded = wh.replace_partition(cfg.clean_table, partition, clean)
    held = wh.replace_partition(cfg.quarantine_table, partition, quarantined)
    return {"partition": partition, "loaded": loaded, "quarantined": held}


def pending_partitions(cfg: Config, today: date) -> list[str]:
    """Partitions after the checkpoint, always including the last `lookback_days` for late arrivals."""
    window_start = today - timedelta(days=cfg.lookback_days)
    last = state.read_checkpoint(cfg)
    start = min(date.fromisoformat(last) + timedelta(days=1), window_start) if last else window_start
    days = (today - start).days
    return [(start + timedelta(days=i)).isoformat() for i in range(days)]


def run(cfg: Config, wh, today: date, partitions: list[str] | None = None) -> list[dict]:
    summaries = []
    for partition in partitions if partitions is not None else pending_partitions(cfg, today):
        summary = process_partition(cfg, wh, partition)
        state.record(cfg, summary)
        obs.log_summary(summary)
        summaries.append(summary)
    return summaries
