"""Shared outbound HTTP client used for all third-party calls."""
import asyncio
import random
from collections.abc import Iterable

import httpx

from app.errors import UpstreamError
from app.logging import log_event
from app.settings import settings

RETRYABLE_STATUS = {502, 503, 504}


def _default_retry_methods() -> frozenset[str]:
    return frozenset(m.strip().upper() for m in settings.http_retry_methods.split(",") if m.strip())


class HttpClient:
    def __init__(self, base_url: str, *, timeout: float = 5.0, max_retries: int | None = None,
                 retry_methods: Iterable[str] | None = None, backoff_base: float = 0.2,
                 headers: dict | None = None):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, headers=headers or {})
        self._max_retries = settings.http_max_retries if max_retries is None else max_retries
        self._retry_methods = (_default_retry_methods() if retry_methods is None
                               else frozenset(m.upper() for m in retry_methods))
        self._backoff_base = backoff_base

    def _retries_for(self, method: str) -> int:
        return self._max_retries if method.upper() in self._retry_methods else 0

    async def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        retries = self._retries_for(method)
        attempt = 0
        while True:
            try:
                resp = await self._client.request(method, path, **kwargs)
                if resp.status_code not in RETRYABLE_STATUS:
                    return resp
                reason = f"status {resp.status_code}"
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                reason = type(exc).__name__
                resp = None
            if attempt >= retries:
                log_event("upstream.giving_up", method=method, path=path, reason=reason)
                if resp is not None:
                    return resp
                raise UpstreamError(f"{method} {path} failed: {reason}")
            delay = self._backoff_base * (2 ** attempt) + random.uniform(0, 0.1)
            log_event("upstream.retry", method=method, path=path, attempt=attempt + 1, reason=reason)
            await asyncio.sleep(delay)
            attempt += 1

    async def get(self, path: str, **kwargs) -> httpx.Response:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs) -> httpx.Response:
        return await self.request("POST", path, **kwargs)

    async def aclose(self) -> None:
        await self._client.aclose()
