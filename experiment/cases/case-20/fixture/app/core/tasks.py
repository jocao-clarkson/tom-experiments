"""Durable background tasks.

enqueue() inserts a row into `tasks` using the caller's session, so the task is committed
(or rolled back) together with the request's own writes. The worker process calls run_once()
in a loop; it claims rows with FOR UPDATE SKIP LOCKED and retries failures with backoff up
to `max_attempts`. Handlers register themselves at import time with @handler.
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


async def run_once(session: AsyncSession) -> bool:
    row = (await session.execute(text(
        "SELECT id, name, payload, attempts, max_attempts FROM tasks "
        "WHERE done_at IS NULL AND run_at <= now() ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED"
    ))).first()
    if row is None:
        return False
    try:
        await HANDLERS[row.name](row.payload)
        await session.execute(text("UPDATE tasks SET done_at = now() WHERE id = :id"), {"id": row.id})
    except Exception:
        attempts = row.attempts + 1
        await session.execute(
            text("UPDATE tasks SET attempts = :a, run_at = now() + make_interval(secs => :d), "
                 "done_at = CASE WHEN :a >= max_attempts THEN now() END WHERE id = :id"),
            {"a": attempts, "d": 2 ** attempts, "id": row.id},
        )
    await session.commit()
    return True
