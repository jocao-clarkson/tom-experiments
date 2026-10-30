import sqlite3
import uuid
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class NotesRepo:
    """All SQL lives in repository classes."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row

    def get_note(self, note_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return dict(row) if row else None

    def get_note_for_owner(self, note_id: str, user_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM notes WHERE id = ? AND owner_id = ?", (note_id, user_id)
        ).fetchone()
        return dict(row) if row else None

    def changed_since(self, user_id: str, since: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM notes WHERE owner_id = ? AND updated_at > ? ORDER BY updated_at",
            (user_id, since),
        ).fetchall()
        return [dict(r) for r in rows]

    def create_note(self, owner_id: str, title: str, body: str) -> dict:
        note = {"id": str(uuid.uuid4()), "owner_id": owner_id, "title": title, "body": body,
                "updated_at": now_iso()}
        self.conn.execute(
            "INSERT INTO notes (id, owner_id, title, body, updated_at) VALUES (:id, :owner_id, :title, :body, :updated_at)",
            note,
        )
        self.conn.commit()
        return note


SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    reminders TEXT,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    payload TEXT NOT NULL,
    dedupe_key TEXT UNIQUE,
    created_at TEXT NOT NULL
);
"""
