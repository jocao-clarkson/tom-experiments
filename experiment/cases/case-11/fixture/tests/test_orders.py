import pytest

from app.errors import NotFoundError
from app.services.orders import OrderService


class FakeRepo:
    def __init__(self, orders):
        self.orders = orders

    async def get(self, order_id):
        return self.orders.get(order_id)


async def test_get_order_returns_row():
    svc = OrderService(FakeRepo({"o1": {"id": "o1", "status": "captured"}}))
    assert (await svc.get_order("o1"))["status"] == "captured"


async def test_get_order_missing_raises():
    with pytest.raises(NotFoundError):
        await OrderService(FakeRepo({})).get_order("nope")
