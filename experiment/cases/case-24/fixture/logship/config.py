import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG = Path.home() / ".config" / "logship" / "config.toml"
DEFAULT_BUNDLE_DIR = Path.home() / ".local" / "share" / "logship" / "bundles"


@dataclass(frozen=True)
class Config:
    bundle_dir: Path
    upload_url: str
    token: str | None


def load_config(path: Path | None = None) -> Config:
    """Load config from TOML, then apply LOGSHIP_* environment overrides."""
    data: dict = {}
    path = path or Path(os.environ.get("LOGSHIP_CONFIG", DEFAULT_CONFIG))
    if path.exists():
        with path.open("rb") as f:
            data = tomllib.load(f)
    bundle_dir = Path(os.environ.get("LOGSHIP_BUNDLE_DIR", data.get("bundle_dir", DEFAULT_BUNDLE_DIR)))
    return Config(
        bundle_dir=bundle_dir.expanduser(),
        upload_url=os.environ.get("LOGSHIP_UPLOAD_URL", data.get("upload_url", "https://logs.internal/upload")),
        token=os.environ.get("LOGSHIP_TOKEN", data.get("token")),
    )
