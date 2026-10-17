import pytest


class FakeWarehouse:
    """In-memory stand-in with the same replace-partition semantics as Warehouse."""

    def __init__(self):
        self.tables: dict[str, dict[str, list[dict]]] = {}

    def replace_partition(self, table, partition, rows):
        self.tables.setdefault(table, {})[partition] = [dict(r) for r in rows]
        return len(rows)

    def rows(self, table):
        return [r for part in self.tables.get(table, {}).values() for r in part]


@pytest.fixture
def warehouse():
    return FakeWarehouse()
