"""Partition summary logging. Ops alerting parses these lines as logfmt integers."""
import logging

log = logging.getLogger("pipeline.runner")

SUMMARY_FIELDS = ("loaded", "quarantined")


def log_summary(summary: dict) -> None:
    counts = " ".join(f"{k}={int(summary.get(k, 0))}" for k in SUMMARY_FIELDS)
    log.info("partition done partition=%s %s", summary["partition"], counts)
