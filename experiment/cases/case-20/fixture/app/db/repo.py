from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_FIELDS = ("kind", "started_at", "duration_s", "distance_m", "client_updated_at", "deleted")


def _params(w: dict) -> dict:
    p = {k: w.get(k) for k in _FIELDS}
    if p["distance_m"] is not None:
        p["distance_m"] = round(p["distance_m"])
    return p


class WorkoutRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_client_id(self, user_id: str, client_id: str) -> dict | None:
        row = (await self.session.execute(
            text("SELECT * FROM workouts WHERE user_id = :u AND client_id = :c"),
            {"u": user_id, "c": client_id},
        )).mappings().first()
        return dict(row) if row else None

    async def insert(self, user_id: str, w: dict) -> str:
        return (await self.session.execute(
            text("INSERT INTO workouts (user_id, client_id, kind, started_at, duration_s, distance_m, "
                 "client_updated_at, deleted, server_updated_at) "
                 "VALUES (:u, :client_id, :kind, :started_at, :duration_s, :distance_m, "
                 ":client_updated_at, :deleted, now()) RETURNING id"),
            {"u": user_id, "client_id": w["client_id"], **_params(w)},
        )).scalar_one()

    async def update(self, workout_id: str, w: dict) -> None:
        await self.session.execute(
            text("UPDATE workouts SET kind = :kind, started_at = :started_at, duration_s = :duration_s, "
                 "distance_m = :distance_m, client_updated_at = :client_updated_at, deleted = :deleted, "
                 "server_updated_at = now() WHERE id = :id"),
            {"id": workout_id, **_params(w)},
        )

    async def changed_since(self, user_id: str, since: datetime, limit: int = 500) -> list[dict]:
        rows = (await self.session.execute(
            text("SELECT * FROM workouts WHERE user_id = :u AND server_updated_at > :s "
                 "ORDER BY server_updated_at LIMIT :l"),
            {"u": user_id, "s": since, "l": limit},
        )).mappings().all()
        return [dict(r) for r in rows]
