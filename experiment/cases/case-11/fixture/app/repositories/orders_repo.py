from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class OrdersRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, order_id: str) -> dict | None:
        row = (await self._session.execute(
            text("SELECT id, status, captured_amount, currency, payment_ref FROM orders WHERE id = :id"),
            {"id": order_id},
        )).mappings().first()
        return dict(row) if row else None

    async def refunded_total(self, order_id: str) -> Decimal:
        total = (await self._session.execute(
            text("SELECT COALESCE(SUM(amount), 0) FROM refunds "
                 "WHERE order_id = :id AND status <> 'failed'"),
            {"id": order_id},
        )).scalar_one()
        return Decimal(total)

    async def insert_refund(self, order_id: str, amount: Decimal, status: str,
                            provider_ref: str | None, reason: str | None = None) -> str:
        refund_id = (await self._session.execute(
            text("INSERT INTO refunds (order_id, amount, status, provider_ref, reason) "
                 "VALUES (:o, :a, :s, :p, :r) RETURNING id"),
            {"o": order_id, "a": amount, "s": status, "p": provider_ref, "r": reason},
        )).scalar_one()
        await self._session.commit()
        return str(refund_id)
