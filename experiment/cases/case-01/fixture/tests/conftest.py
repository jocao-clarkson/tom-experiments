import pytest

from orders import create_app
from orders.http_client import ResilientClient
from orders.repository import OrderRepository


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeSession:
    """Scripted stand-in for requests.Session used by ResilientClient."""

    def __init__(self):
        self.calls = []
        self.script = []

    def queue(self, item):
        self.script.append(item)

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def repo():
    return OrderRepository()


@pytest.fixture
def fake_session():
    return FakeSession()


@pytest.fixture
def payments(fake_session):
    return ResilientClient("https://payfast.test", "test-key", session=fake_session, backoff_base=0)


@pytest.fixture
def client(repo, payments):
    return create_app(repo, payments).test_client()
