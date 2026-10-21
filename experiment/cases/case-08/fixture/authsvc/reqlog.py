import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger("authsvc.http")


def _redact_bearer(header: str) -> str:
    """Keep the JWT header and claims for debugging; replace the signature."""
    head, dot, _signature = header.rpartition(".")
    return f"{head}{dot}<redacted>" if dot else header


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        started = time.perf_counter()
        auth = request.headers.get("authorization")
        if auth:
            log.debug("%s %s authorization=%s", request.method, request.url.path, _redact_bearer(auth))
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        log.info("%s %s %s %.1fms", request.method, request.url.path, response.status_code, elapsed_ms)
        return response
