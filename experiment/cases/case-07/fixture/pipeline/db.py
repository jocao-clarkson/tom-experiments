import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Database:
    def __init__(self, path: Path | str):
        self.conn = sqlite3.connect(str(path), isolation_level=None)
        self.conn.row_factory = sqlite3.Row

    @contextmanager
    def transaction(self):
        self.conn.execute("BEGIN")
        try:
            yield self
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        else:
            self.conn.execute("COMMIT")

    def upsert(self, table: str, rows: list[dict], key: tuple[str, ...], chunk_size: int = 5000) -> int:
        """Insert rows, updating non-key columns on key conflict. Call inside transaction()."""
        if not rows:
            return 0
        cols = list(rows[0].keys())
        updates = ", ".join(f"{c} = excluded.{c}" for c in cols if c not in key)
        sql = (
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)}) "
            f"ON CONFLICT ({', '.join(key)}) DO UPDATE SET {updates}"
        )
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i : i + chunk_size]
            self.conn.executemany(sql, [tuple(r[c] for c in cols) for r in chunk])
        return len(rows)

    def existing_values(self, table: str, column: str) -> set[str]:
        return {r[0] for r in self.conn.execute(f"SELECT {column} FROM {table}")}
