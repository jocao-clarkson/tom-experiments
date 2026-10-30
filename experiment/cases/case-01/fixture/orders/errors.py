from flask import jsonify


class AppError(Exception):
    status = 500
    code = "internal_error"

    def __init__(self, message, *, code=None, details=None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details or {}


class ValidationError(AppError):
    status = 422
    code = "validation_failed"


class NotFoundError(AppError):
    status = 404
    code = "not_found"


class ConflictError(AppError):
    status = 409
    code = "conflict"


class UpstreamError(AppError):
    status = 502
    code = "upstream_error"


def error_response(err: AppError):
    body = {"error": {"code": err.code, "message": err.message}}
    if err.details:
        body["error"]["details"] = err.details
    return jsonify(body), err.status
