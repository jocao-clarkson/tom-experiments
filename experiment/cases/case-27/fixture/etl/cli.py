import argparse
import logging
import sys
from datetime import date

import psycopg

from . import config
from .events import LocalStorage, S3Storage
from .jobs import JOBS
from .warehouse import Warehouse


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="etl")
    p.add_argument("job", choices=sorted(JOBS))
    p.add_argument("--run-date", type=date.fromisoformat)
    p.add_argument("--local-root", help="read events from a local directory instead of S3")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    cfg = config.load(args.run_date)
    if args.local_root:
        storage = LocalStorage(args.local_root)
    else:
        storage = S3Storage(cfg.events_bucket)
    with psycopg.connect(cfg.warehouse_dsn) as conn:
        ok = JOBS[args.job](cfg, storage, Warehouse(conn))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
