import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone


class StockRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS items (
                    sku TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    on_hand INTEGER NOT NULL DEFAULT 0,
                    reorder_point INTEGER NOT NULL DEFAULT 0
                );
                """
            )

    def get_item(self, sku: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM items WHERE sku = ?", (sku,)).fetchone()
            return dict(row) if row else None

    def list_items(self) -> list[dict]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM items ORDER BY sku")]

    def adjust_on_hand(self, sku: str, delta: int) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE items SET on_hand = on_hand + ? WHERE sku = ?", (delta, sku))

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()
