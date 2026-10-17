import re
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DropFile:
    path: Path
    groups: dict


class DropFolder:
    """Files land in drop_dir via SFTP; processed files move to archive_dir."""

    def __init__(self, drop_dir: Path, archive_dir: Path):
        self.drop_dir = drop_dir
        self.archive_dir = archive_dir

    def discover(self, pattern: str) -> list[DropFile]:
        rx = re.compile(pattern)
        found = []
        for p in sorted(self.drop_dir.iterdir()):
            if not p.is_file():
                continue
            m = rx.fullmatch(p.name)
            if m:
                found.append(DropFile(path=p, groups=m.groupdict()))
        return found

    def archive(self, f: DropFile) -> Path:
        return self._move(f, self.archive_dir)

    def _move(self, f: DropFile, dest_dir: Path) -> Path:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f.path.name
        if dest.exists():
            dest.unlink()
        shutil.move(str(f.path), dest)
        return dest
