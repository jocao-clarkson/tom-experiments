from dataclasses import dataclass

from fastapi import Header, HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.settings import settings
from pacer_auth import verify_access_token

engine = create_async_engine(settings.database_url, pool_size=20)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@dataclass(frozen=True)
class CurrentUser:
    id: str


async def get_session():
    async with SessionLocal() as session:
        yield session


async def current_user(authorization: str = Header(default="")) -> CurrentUser:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    claims = verify_access_token(authorization.removeprefix("Bearer "))
    if claims is None:
        raise HTTPException(status_code=401, detail="invalid token")
    return CurrentUser(id=claims["sub"])
