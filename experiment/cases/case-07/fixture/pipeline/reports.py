import csv
from pathlib import Path

from .validate import Reject


def write_reject_report(reports_dir: Path, source_name: str, rejects: list[Reject]) -> Path | None:
    """Write <source_name>.rejects.csv with line, reason and the original values."""
    if not rejects:
        return None
    reports_dir.mkdir(parents=True, exist_ok=True)
    out = reports_dir / f"{source_name}.rejects.csv"
    fieldnames = ["line", "reason"] + sorted({k for r in rejects for k in r.row})
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rejects:
            w.writerow({"line": r.line, "reason": r.reason, **r.row})
    return out
