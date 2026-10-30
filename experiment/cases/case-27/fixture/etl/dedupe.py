from typing import Iterable, Iterator


def dedupe_by(events: Iterable[dict], key: str = "event_id") -> Iterator[dict]:
    """Drop repeats of the same key within one pass (clients retry uploads)."""
    seen: set = set()
    for e in events:
        k = e.get(key)
        if k in seen:
            continue
        seen.add(k)
        yield e
