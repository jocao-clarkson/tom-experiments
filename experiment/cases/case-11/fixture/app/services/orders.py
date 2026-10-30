from app.errors import NotFoundError
from app.repositories.orders_repo import OrdersRepository


class OrderService:
    def __init__(self, repo: OrdersRepository):
        self._repo = repo

    async def get_order(self, order_id: str) -> dict:
        order = await self._repo.get(order_id)
        if order is None:
            raise NotFoundError(f"order {order_id} not found")
        return order
