import json
import sqlite3

from .db import now_iso


def enqueue(conn: sqlite3.Connection, name: str, payload: dict, dedupe_key: str | None = None) -> bool:
    """Insert a job row for the worker fleet. With a dedupe_key, a second
    enqueue of the same key is a no-op and returns False."""
    try:
        conn.execute(
            "INSERT INTO jobs (name, payload, dedupe_key, created_at) VALUES (?, ?, ?, ?)",
            (name, json.dumps(payload), dedupe_key, now_iso()),
        )
    except sqlite3.IntegrityError:
        return False
    conn.commit()
    return True
