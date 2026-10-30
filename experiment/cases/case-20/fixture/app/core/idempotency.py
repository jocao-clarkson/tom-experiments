"""Idempotency-Key support for mutating endpoints.

Responses are stored per (user, key). A repeated request with the same key gets the stored
status and body without re-running the handler.
"""
import json

from fastapi import Request, Response
from sqlalchemy import text


async def replay_or_none(session, user_id: str, key: str) -> Response | None:
    row = (await session.execute(
        text("SELECT status, body FROM idempotency_keys WHERE user_id = :u AND key = :k"),
        {"u": user_id, "k": key},
    )).first()
    if row is None:
        return None
    return Response(content=row.body, status_code=row.status, media_type="application/json")


async def remember(session, user_id: str, key: str, status: int, body: dict) -> None:
    await session.execute(
        text("INSERT INTO idempotency_keys (user_id, key, status, body) VALUES (:u, :k, :s, :b) "
             "ON CONFLICT (user_id, key) DO NOTHING"),
        {"u": user_id, "k": key, "s": status, "b": json.dumps(body, default=str)},
    )


def idempotency_key(request: Request) -> str | None:
    return request.headers.get("idempotency-key")
