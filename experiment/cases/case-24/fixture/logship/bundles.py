import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

PREFIX = "bundle-"
SUFFIX = ".tar.gz"
MARKER = ".uploaded"
STAMP = "%Y%m%dT%H%M%SZ"


@dataclass(frozen=True)
class Bundle:
    path: Path
    created_at: datetime
    size: int
    uploaded: bool

    @property
    def marker(self) -> Path:
        return self.path.with_name(self.path.name + MARKER)


def bundle_name(at: datetime) -> str:
    return f"{PREFIX}{at.astimezone(timezone.utc).strftime(STAMP)}{SUFFIX}"


def parse_created_at(name: str) -> datetime | None:
    if not (name.startswith(PREFIX) and name.endswith(SUFFIX)):
        return None
    stamp = name[len(PREFIX):-len(SUFFIX)]
    try:
        return datetime.strptime(stamp, STAMP).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def list_bundles(bundle_dir: Path) -> list[Bundle]:
    """Bundles in bundle_dir, oldest first. Files that don't match the naming
    scheme are ignored."""
    if not bundle_dir.is_dir():
        return []
    found = []
    for entry in bundle_dir.iterdir():
        created = parse_created_at(entry.name)
        if created is None or not entry.is_file():
            continue
        found.append(Bundle(
            path=entry,
            created_at=created,
            size=entry.stat().st_size,
            uploaded=entry.with_name(entry.name + MARKER).exists(),
        ))
    return sorted(found, key=lambda b: b.created_at)


def create_bundle(bundle_dir: Path, sources: list[Path], now: datetime) -> Path:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    target = bundle_dir / bundle_name(now)
    with tarfile.open(target, "w:gz") as tar:
        for src in sources:
            tar.add(src, arcname=src.name)
    return target


def mark_uploaded(bundle: Bundle) -> None:
    bundle.marker.touch()
