import logging

from fastapi import FastAPI

from .reqlog import RequestLogMiddleware
from .routes import recovery
from .settings import get_settings


def create_app(db) -> FastAPI:
    """db must provide transaction() -> context manager yielding a connection."""
    settings = get_settings()
    logging.getLogger("authsvc").setLevel(settings.log_level)
    app = FastAPI(title="authsvc")
    app.state.db = db
    app.add_middleware(RequestLogMiddleware)
    app.include_router(recovery.router)
    return app
