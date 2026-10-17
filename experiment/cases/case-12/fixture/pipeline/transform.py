from datetime import datetime
from decimal import Decimal

REQUIRED = ("event_id", "event_type", "occurred_at", "user_id")


def normalize(events):
    """Split raw events into (clean_rows, quarantined_rows).

    Quarantined rows carry a `reason` so analysts can see why they were held back.
    """
    clean, quarantined = [], []
    seen = set()
    for ev in events:
        missing = [f for f in REQUIRED if not ev.get(f)]
        if missing:
            quarantined.append({**ev, "reason": f"missing_fields:{','.join(missing)}"})
            continue
        if ev["event_id"] in seen:
            continue
        seen.add(ev["event_id"])
        row = {
            "event_id": ev["event_id"],
            "event_type": ev["event_type"].lower(),
            "occurred_at": datetime.fromisoformat(ev["occurred_at"].replace("Z", "+00:00")),
            "user_id": str(ev["user_id"]),
            "amount": Decimal(str(ev["amount"])) if ev.get("amount") is not None else None,
            "currency": (ev.get("currency") or "").upper() or None,
        }
        clean.append(row)
    return clean, quarantined
