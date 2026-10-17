from datetime import date
from typing import Sequence


class Warehouse:
    """Writes whole day partitions. replace_partition is idempotent: running a
    job twice for the same day leaves the same rows."""

    def __init__(self, conn, paramstyle: str = "%s"):
        self.conn = conn
        self.ph = paramstyle

    def replace_partition(self, table: str, day: date, columns: Sequence[str], rows: list[tuple]) -> int:
        cols = ", ".join(columns)
        marks = ", ".join([self.ph] * len(columns))
        cur = self.conn.cursor()
        try:
            cur.execute(f"DELETE FROM {table} WHERE day = {self.ph}", (day.isoformat(),))
            if rows:
                cur.executemany(f"INSERT INTO {table} ({cols}) VALUES ({marks})", rows)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return len(rows)
