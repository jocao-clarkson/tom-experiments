import argparse
import logging
import sys

from . import config
from .db import Database
from .jobs import inventory_import

JOBS = {
    "inventory_import": inventory_import.run,
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="merch-batch")
    parser.add_argument("job", choices=sorted(JOBS))
    parser.add_argument("--config")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    cfg = config.load(args.job, args.config)
    db = Database(cfg.db_path)
    outcomes = JOBS[args.job](cfg, db)
    for o in outcomes:
        print(f"{o.name}: loaded={o.loaded} rejected={o.rejected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
