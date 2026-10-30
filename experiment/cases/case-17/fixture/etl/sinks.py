import csv
import os
import shutil
import tempfile
from pathlib import Path


def write_partition(output_dir: Path, dataset: str, day: str, rows: list[dict]) -> int:
    """Write rows to output_dir/<dataset>/dt=<day>/part-0.csv, replacing the partition atomically.

    Rows are written into a temp directory beside the target and swapped in with a rename,
    so readers never see a half-written partition and reruns replace earlier output.
    """
    target = output_dir / dataset / f"dt={day}"
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent))
    try:
        with (tmp / "part-0.csv").open("w", newline="", encoding="utf-8") as fh:
            if rows:
                writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
        if target.exists():
            old = target.with_name(target.name + ".old")
            os.replace(target, old)
            os.replace(tmp, target)
            shutil.rmtree(old)
        else:
            os.replace(tmp, target)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return len(rows)
