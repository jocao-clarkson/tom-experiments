from collections import defaultdict
from datetime import timedelta
from typing import Iterable


def sessionize(events: Iterable[dict], gap_minutes: int) -> list[dict]:
    """Group events per visitor into sessions split by inactivity gaps."""
    gap = timedelta(minutes=gap_minutes)
    by_visitor: dict[str, list[dict]] = defaultdict(list)
    for ev in events:
        by_visitor[ev["visitor_id"]].append(ev)

    sessions = []
    for visitor, evs in by_visitor.items():
        evs.sort(key=lambda e: e["ts"])
        current = [evs[0]]
        for ev in evs[1:]:
            if ev["ts"] - current[-1]["ts"] > gap:
                sessions.append(_summarise(visitor, current))
                current = []
            current.append(ev)
        sessions.append(_summarise(visitor, current))
    return sessions


def _summarise(visitor: str, evs: list[dict]) -> dict:
    return {
        "visitor_id": visitor,
        "session_start": evs[0]["ts"].isoformat(),
        "session_end": evs[-1]["ts"].isoformat(),
        "pageviews": len(evs),
        "landing_url": evs[0]["url"],
    }
