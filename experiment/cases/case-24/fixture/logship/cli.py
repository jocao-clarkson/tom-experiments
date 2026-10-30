import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .bundles import create_bundle, list_bundles
from .config import load_config
from .output import Output

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2


def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n} B"


def cmd_list(args, cfg, out: Output) -> int:
    bundles = list_bundles(cfg.bundle_dir)
    for b in bundles:
        flag = "uploaded" if b.uploaded else "pending"
        out.info(f"{b.path.name}  {_human_size(b.size):>9}  {flag}")
    out.result(
        {"bundles": [{"name": b.path.name, "size": b.size, "uploaded": b.uploaded,
                      "created_at": b.created_at.isoformat()} for b in bundles]},
        f"{len(bundles)} bundle(s) in {cfg.bundle_dir}",
    )
    return EXIT_OK


def cmd_bundle(args, cfg, out: Output) -> int:
    sources = [Path(p) for p in args.paths]
    missing = [str(p) for p in sources if not p.exists()]
    if missing:
        out.error(f"no such file: {', '.join(missing)}")
        return EXIT_USAGE
    path = create_bundle(cfg.bundle_dir, sources, datetime.now(timezone.utc))
    out.result({"bundle": path.name}, f"created {path.name}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="logship")
    p.add_argument("--version", action="version", version=f"logship {__version__}")
    p.add_argument("--config", type=Path, help="path to config.toml")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("-q", "--quiet", action="store_true", help="only print errors")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("list", help="list local bundles")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("bundle", help="bundle log files")
    sp.add_argument("paths", nargs="+")
    sp.set_defaults(func=cmd_bundle)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    out = Output(json_mode=args.json, quiet=args.quiet)
    cfg = load_config(args.config)
    return args.func(args, cfg, out)


if __name__ == "__main__":
    sys.exit(main())
