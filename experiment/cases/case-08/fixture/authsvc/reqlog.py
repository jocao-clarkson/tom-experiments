import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware

from .redact import mask_bearer

log = logging.getLogger("authsvc.http")


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        started = time.perf_counter()
        auth = request.headers.get("authorization")
        if auth:
            log.debug("%s %s authorization=%s", request.method, request.url.path, mask_bearer(auth))
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        log.info("%s %s %s %.1fms", request.method, request.url.path, response.status_code, elapsed_ms)
        return response
