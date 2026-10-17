import csv
import logging
from dataclasses import dataclass

from ..config import JobConfig
from ..db import Database
from ..reports import write_reject_report
from ..sources import DropFolder
from ..validate import Validator

log = logging.getLogger(__name__)

PATTERN = r"inventory_(?P<warehouse>[a-z0-9]+)_(?P<date>\d{8})\.csv"


@dataclass
class FileOutcome:
    name: str
    loaded: int
    rejected: int


def _qty_rule(row):
    try:
        return None if int(row["qty"]) >= 0 else "qty_negative"
    except ValueError:
        return "qty_not_integer"


def run(cfg: JobConfig, db: Database) -> list[FileOutcome]:
    folder = DropFolder(cfg.drop_dir / "inventory", cfg.archive_dir / "inventory")
    known_skus = db.existing_values("products", "sku")
    validator = Validator(
        required=["sku", "qty"],
        rules=[lambda r: None if r["sku"] in known_skus else "unknown_sku", _qty_rule],
    )
    outcomes = []
    for f in folder.discover(PATTERN):
        with f.path.open(newline="", encoding="utf-8") as fh:
            result = validator.run(csv.DictReader(fh))
        rows = [
            {"warehouse": f.groups["warehouse"], "sku": r["sku"], "qty": int(r["qty"]), "as_of": f.groups["date"]}
            for r in result.valid
        ]
        with db.transaction():
            db.upsert("inventory", rows, key=("warehouse", "sku"), chunk_size=cfg.upsert_chunk_size)
        write_reject_report(cfg.reports_dir / "inventory", f.path.stem, result.rejects)
        folder.archive(f)
        log.info("inventory file loaded", extra={"file": f.path.name, "rows": len(rows), "rejects": len(result.rejects)})
        outcomes.append(FileOutcome(f.path.name, len(rows), len(result.rejects)))
    return outcomes
