import sqlite3

from flask import Flask, jsonify


class APIError(Exception):
    status = 500
    code = "internal_error"

    def __init__(self, message: str = "", **details):
        super().__init__(message or self.code)
        self.message = message or self.code
        self.details = details

    def to_response(self):
        body = {"error": {"code": self.code, "message": self.message}}
        if self.details:
            body["error"]["details"] = self.details
        return jsonify(body), self.status


class ValidationFailed(APIError):
    status = 400
    code = "validation_failed"


class NotFound(APIError):
    status = 404
    code = "not_found"


class Conflict(APIError):
    status = 409
    code = "conflict"


class UpstreamError(APIError):
    status = 502
    code = "upstream_error"


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(APIError)
    def _handle(err: APIError):
        return err.to_response()

    @app.errorhandler(sqlite3.OperationalError)
    def _handle_db(err: sqlite3.OperationalError):
        return jsonify({"error": {"code": "unavailable", "message": "database busy"}}), 503
