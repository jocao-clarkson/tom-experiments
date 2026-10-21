import pytest

from orders import create_app
from orders.repository import OrderRepository
from orders.settings import DEFAULTS, build_payments_client


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
    settings = dict(
        DEFAULTS,
        PAYFAST_BASE_URL="https://payfast.test",
        PAYFAST_API_KEY="test-key",
        PAYFAST_BACKOFF=0,
    )
    return build_payments_client(settings, session=fake_session)


@pytest.fixture
def client(repo, payments):
    return create_app(repo, payments).test_client()
