"""Warehouse writes. Partitions are replaced wholesale so reruns are safe."""


class Warehouse:
    def __init__(self, conn):
        self._conn = conn

    def replace_partition(self, table: str, partition: str, rows: list[dict]) -> int:
        with self._conn.cursor() as cur:
            cur.execute(f"DELETE FROM {table} WHERE partition_date = %s", (partition,))
            if rows:
                cols = list(rows[0].keys())
                placeholders = ", ".join(["%s"] * (len(cols) + 1))
                cur.executemany(
                    f"INSERT INTO {table} ({', '.join(cols)}, partition_date) VALUES ({placeholders})",
                    [tuple(r[c] for c in cols) + (partition,) for r in rows],
                )
        self._conn.commit()
        return len(rows)

    def query(self, sql: str, params: tuple = ()) -> list[tuple]:
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
