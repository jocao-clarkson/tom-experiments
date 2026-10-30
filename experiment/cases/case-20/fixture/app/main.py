import asyncio

from fastapi import FastAPI
from sqlalchemy import text

from app.api import workouts
from app.core import tasks
from app.core.settings import settings
from app.deps import SessionLocal

app = FastAPI(title="pacer-api")
app.include_router(workouts.router)


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@tasks.handler("maintenance.purge_idempotency_keys")
async def purge_idempotency_keys(payload: dict) -> None:
    async with SessionLocal() as session:
        await session.execute(
            text("DELETE FROM idempotency_keys WHERE created_at < now() - make_interval(hours => :h)"),
            {"h": settings.idempotency_ttl_hours},
        )
        await session.commit()


async def run_worker() -> None:
    while True:
        async with SessionLocal() as session:
            if not await tasks.run_once(session):
                await asyncio.sleep(1.0)
