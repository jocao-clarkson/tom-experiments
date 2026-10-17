"""Durable background tasks.

enqueue() inserts a row into `tasks` using the caller's session, so the task is committed
(or rolled back) together with the request's own writes. The worker process
(`python -m app.worker`) claims rows with FOR UPDATE SKIP LOCKED and retries failures
with backoff up to `max_attempts`.
"""
import json
from typing import Awaitable, Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

HANDLERS: dict[str, Callable[[dict], Awaitable[None]]] = {}


def handler(name: str):
    def register(fn):
        HANDLERS[name] = fn
        return fn
    return register


async def enqueue(session: AsyncSession, name: str, payload: dict, *, max_attempts: int = 5) -> None:
    if name not in HANDLERS:
        raise KeyError(f"unknown task {name}")
    await session.execute(
        text("INSERT INTO tasks (name, payload, max_attempts) VALUES (:n, CAST(:p AS jsonb), :m)"),
        {"n": name, "p": json.dumps(payload), "m": max_attempts},
    )
