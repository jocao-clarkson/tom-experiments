import logging
import os
import socket

log = logging.getLogger("etl.metrics")
_ADDR = (os.environ.get("STATSD_HOST", "127.0.0.1"), int(os.environ.get("STATSD_PORT", "8125")))
_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def emit(name: str, value: float, tags: dict[str, str] | None = None, kind: str = "g") -> None:
    tag_str = ",".join(f"{k}:{v}" for k, v in sorted((tags or {}).items()))
    payload = f"etl.{name}:{value}|{kind}" + (f"|#{tag_str}" if tag_str else "")
    try:
        _sock.sendto(payload.encode(), _ADDR)
    except OSError as exc:
        log.debug("metric send failed: %s", exc)
