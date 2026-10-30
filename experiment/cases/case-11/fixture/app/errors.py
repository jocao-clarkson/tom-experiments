from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str = "", *, details: dict | None = None):
        super().__init__(message)
        self.message = message or self.code
        self.details = details or {}


class NotFoundError(ApiError):
    status_code = 404
    code = "not_found"


class ValidationError(ApiError):
    status_code = 422
    code = "validation_failed"


class ConflictError(ApiError):
    status_code = 409
    code = "conflict"


class UpstreamError(ApiError):
    status_code = 502
    code = "upstream_error"


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    body = {"error": {"code": exc.code, "message": exc.message}}
    if exc.details:
        body["error"]["details"] = exc.details
    return JSONResponse(status_code=exc.status_code, content=body)
