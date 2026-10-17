"""Push gateway client."""
import time

import httpx

from app.core import tasks
from app.core.settings import settings

_client = httpx.Client(timeout=10.0)


def send_silent(user_id: str, data: dict, *, exclude_device: str | None = None) -> None:
    """Send a content-available push to all of a user's devices. Blocks until the gateway answers."""
    body = {"user_id": user_id, "silent": True, "data": data, "exclude_device": exclude_device}
    headers = {"authorization": f"Bearer {settings.push_gateway_token}"}
    for attempt in range(3):
        resp = _client.post(settings.push_gateway_url, json=body, headers=headers)
        if resp.status_code < 500:
            resp.raise_for_status()
            return
        time.sleep(0.5 * (attempt + 1))
    resp.raise_for_status()


@tasks.handler("push.silent")
async def _silent_task(payload: dict) -> None:
    send_silent(payload["user_id"], payload.get("data", {}), exclude_device=payload.get("exclude_device"))
