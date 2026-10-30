import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    charge_id TEXT,
    captured_cents INTEGER NOT NULL DEFAULT 0,
    currency TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS refunds (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(id),
    amount_cents INTEGER NOT NULL,
    reason TEXT,
    status TEXT NOT NULL,
    provider_ref TEXT,
    created_at TEXT NOT NULL
);
"""


class OrderRepository:
    def __init__(self, path=":memory:"):
        self.conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    @contextmanager
    def transaction(self):
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield self
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def get_order(self, order_id):
        row = self.conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        return dict(row) if row else None

    def insert_order(self, order):
        self.conn.execute(
            "INSERT INTO orders (id, customer_id, charge_id, captured_cents, currency, status)"
            " VALUES (:id, :customer_id, :charge_id, :captured_cents, :currency, :status)",
            order,
        )

    def list_refunds(self, order_id):
        rows = self.conn.execute(
            "SELECT * FROM refunds WHERE order_id = ? ORDER BY created_at DESC", (order_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def insert_refund(self, refund):
        refund.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        self.conn.execute(
            "INSERT INTO refunds (id, order_id, amount_cents, reason, status, provider_ref, created_at)"
            " VALUES (:id, :order_id, :amount_cents, :reason, :status, :provider_ref, :created_at)",
            refund,
        )
        return refund

    def update_refund(self, refund_id, *, status, provider_ref=None):
        self.conn.execute(
            "UPDATE refunds SET status = ?, provider_ref = COALESCE(?, provider_ref) WHERE id = ?",
            (status, provider_ref, refund_id),
        )
