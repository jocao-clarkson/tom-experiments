from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.core import idempotency
from app.db.repo import WorkoutRepo
from app.deps import current_user, get_session
from app.services import push

router = APIRouter(prefix="/v2/workouts")


class WorkoutIn(BaseModel):
    client_id: str = Field(min_length=8, max_length=64)
    kind: str
    started_at: datetime
    duration_s: int = Field(ge=0, le=86_400)
    distance_m: float | None = Field(default=None, ge=0)
    client_updated_at: datetime
    deleted: bool = False


@router.post("", status_code=201)
async def create_workout(body: WorkoutIn, request: Request, user=Depends(current_user),
                         session=Depends(get_session), x_device_id: str | None = Header(default=None)):
    key = idempotency.idempotency_key(request)
    if key and (replayed := await idempotency.replay_or_none(session, user.id, key)):
        return replayed
    repo = WorkoutRepo(session)
    if await repo.get_by_client_id(user.id, body.client_id):
        raise HTTPException(status_code=409, detail="workout already exists")
    workout_id = await repo.insert(user.id, body.model_dump())
    result = {"id": str(workout_id), "client_id": body.client_id}
    if key:
        await idempotency.remember(session, user.id, key, 201, result)
    await session.commit()
    await push.send_silent(user.id, {"reason": "workouts_changed"}, exclude_device=x_device_id)
    return result
