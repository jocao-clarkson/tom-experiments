"""Push gateway client."""
import httpx

from app.core.settings import settings

_client = httpx.AsyncClient(timeout=settings.push_timeout_s)


async def send_silent(user_id: str, data: dict, *, exclude_device: str | None = None) -> None:
    """Send a content-available push to all of a user's devices, optionally skipping one."""
    body = {"user_id": user_id, "silent": True, "data": data, "exclude_device": exclude_device}
    headers = {"authorization": f"Bearer {settings.push_gateway_token}"}
    resp = await _client.post(settings.push_gateway_url, json=body, headers=headers)
    resp.raise_for_status()
