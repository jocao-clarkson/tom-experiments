import logging
from collections import defaultdict
from datetime import date

from .. import metrics
from ..config import JobConfig
from ..dedupe import dedupe_by
from ..events import ReadStats, Storage, read_events
from ..warehouse import Warehouse

log = logging.getLogger(__name__)

TABLE = "sessions_daily"
COLUMNS = ("day", "platform", "sessions", "users")
MAX_MALFORMED_RATIO = 0.01


class PartitionRejected(Exception):
    pass


def build_day(storage: Storage, day: date) -> tuple[list[tuple], ReadStats]:
    stats = ReadStats()
    sessions = defaultdict(int)
    users = defaultdict(set)
    for e in dedupe_by(read_events(storage, day, stats)):
        if e.get("type") != "session_start":
            continue
        platform = e.get("platform") or "unknown"
        sessions[platform] += 1
        users[platform].add(e.get("user_id"))
    if stats.malformed_ratio > MAX_MALFORMED_RATIO:
        raise PartitionRejected(f"{day}: {stats.malformed}/{stats.lines} malformed lines")
    rows = [(day.isoformat(), p, sessions[p], len(users[p])) for p in sorted(sessions)]
    return rows, stats


def run(cfg: JobConfig, storage: Storage, wh: Warehouse) -> bool:
    """Rebuild each day in the lookback window. A rejected day keeps its
    previous partition; the other days are still processed."""
    ok = True
    for day in cfg.days():
        try:
            rows, stats = build_day(storage, day)
        except PartitionRejected as exc:
            log.error("skipping partition: %s", exc)
            metrics.emit("partition_rejected", 1, {"job": "daily_sessions"}, kind="c")
            ok = False
            continue
        written = wh.replace_partition(TABLE, day, COLUMNS, rows)
        metrics.emit("rows_written", written, {"job": "daily_sessions", "day": day.isoformat()})
        metrics.emit("malformed_lines", stats.malformed, {"job": "daily_sessions"})
        log.info("%s: wrote %d rows from %d files", day, written, len(stats.files))
    return ok
