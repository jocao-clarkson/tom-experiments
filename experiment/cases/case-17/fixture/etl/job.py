import argparse
import logging
import sys
from datetime import date, timedelta

from etl import config as config_mod
from etl.io import read_events
from etl.metrics import Metrics
from etl.sessionize import sessionize
from etl.sinks import write_partition

log = logging.getLogger("etl.job")


def run(cfg: config_mod.JobConfig, day: str, metrics: Metrics) -> dict:
    processed = 0

    def counted(events):
        nonlocal processed
        for ev in events:
            processed += 1
            yield ev

    sessions = sessionize(counted(read_events(cfg.input_dir, day)), cfg.session_gap_minutes)
    written = write_partition(cfg.output_dir, "sessions", day, sessions)
    metrics.incr("events.processed", processed)
    metrics.incr("sessions.written", written)
    metrics.flush()
    summary = {"day": day, "events": processed, "sessions": written}
    log.info("job complete %s", summary)
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="sessions-job")
    parser.add_argument("--config", default="job.toml")
    parser.add_argument("--day", default=(date.today() - timedelta(days=1)).isoformat())
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    cfg = config_mod.load(args.config)
    run(cfg, args.day, Metrics(cfg.statsd_host, cfg.statsd_port))
    return 0


if __name__ == "__main__":
    sys.exit(main())
