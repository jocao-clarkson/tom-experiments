import httpx
import pytest
import respx

from app.clients.http import HttpClient
from app.errors import UpstreamError


@respx.mock
async def test_retries_on_503_then_succeeds():
    route = respx.get("https://svc.test/ping").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"ok": True})]
    )
    client = HttpClient("https://svc.test", backoff_base=0)
    resp = await client.get("/ping")
    assert resp.status_code == 200
    assert route.call_count == 2


@respx.mock
async def test_raises_upstream_error_after_timeouts():
    respx.get("https://svc.test/ping").mock(side_effect=httpx.ReadTimeout("slow"))
    client = HttpClient("https://svc.test", backoff_base=0, max_retries=1)
    with pytest.raises(UpstreamError):
        await client.get("/ping")
