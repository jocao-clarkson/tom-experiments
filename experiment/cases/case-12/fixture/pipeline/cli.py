import argparse
import sys
from datetime import date

import psycopg

from pipeline.config import load_config
from pipeline.load import Warehouse
from pipeline.runner import run
from pipeline.state import run_lock


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="events-pipeline")
    parser.add_argument("--config", default="pipeline.yaml")
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    with run_lock(cfg), psycopg.connect(cfg.warehouse_dsn) as conn:
        run(cfg, Warehouse(conn), date.today())
    return 0


if __name__ == "__main__":
    sys.exit(main())
