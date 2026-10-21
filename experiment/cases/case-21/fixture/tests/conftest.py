import pytest

from inventory import create_app
from inventory.supplier_client import SupplierClient


class FakeResponse:
    def __init__(self, status_code: int, body: dict | None = None):
        self.status_code = status_code
        self._body = body or {}

    def json(self):
        return self._body


class FakeSession:
    """Scripted stand-in for requests.Session used by SupplierClient."""

    def __init__(self):
        self.responses = []
        self.calls = []

    def queue(self, item):
        self.responses.append(item)

    def request(self, method, url, json=None, headers=None, timeout=None):
        self.calls.append({"method": method, "url": url, "json": json})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def fake_session():
    return FakeSession()


@pytest.fixture
def app(tmp_path, fake_session):
    supplier = SupplierClient("https://supplier.test", "k", session=fake_session)
    app = create_app(str(tmp_path / "test.db"), supplier=supplier)
    repo = app.extensions["inventory_service"].repo
    with repo.connect() as conn:
        conn.execute(
            "INSERT INTO items (sku, name, on_hand, reorder_point) VALUES ('A-1', 'Widget', 5, 10)"
        )
    return app


@pytest.fixture
def client(app):
    return app.test_client()
