import socket


class Metrics:
    """Minimal statsd client. Counters are buffered and flushed at the end of the job."""

    def __init__(self, host: str, port: int, prefix: str = "sessions_job"):
        self._addr = (host, port)
        self._prefix = prefix
        self._counters: dict[tuple, int] = {}

    def incr(self, name: str, value: int = 1, **tags: str) -> None:
        key = (name, tuple(sorted(tags.items())))
        self._counters[key] = self._counters.get(key, 0) + value

    def flush(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            for (name, tags), value in self._counters.items():
                tag_str = ",".join(f"{k}:{v}" for k, v in tags)
                line = f"{self._prefix}.{name}:{value}|c" + (f"|#{tag_str}" if tag_str else "")
                sock.sendto(line.encode(), self._addr)
        finally:
            sock.close()
            self._counters.clear()


class RecordingMetrics(Metrics):
    """Test double that keeps counters instead of sending them."""

    def __init__(self):
        super().__init__("127.0.0.1", 0)
        self.flushed: dict[tuple, int] = {}

    def flush(self) -> None:
        self.flushed.update(self._counters)
        self._counters.clear()
