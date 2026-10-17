from fastapi import Depends, FastAPI

from app.clients.http import HttpClient
from app.errors import ApiError, api_error_handler
from app.repositories.orders_repo import OrdersRepository
from app.services.orders import OrderService
from app.settings import settings
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

engine = create_async_engine(settings.database_url, pool_size=10)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session():
    async with SessionLocal() as session:
        yield session


app = FastAPI(title="orders-api")
app.add_exception_handler(ApiError, api_error_handler)

fraud_client = HttpClient(settings.fraud_base_url, timeout=2.0)


def order_service(session=Depends(get_session)) -> OrderService:
    return OrderService(OrdersRepository(session))


@app.get("/orders/{order_id}")
async def get_order(order_id: str, svc: OrderService = Depends(order_service)):
    return await svc.get_order(order_id)
