from fastapi import FastAPI

from .routes import recovery


def create_app(db) -> FastAPI:
    """db must provide transaction() -> context manager yielding a connection."""
    app = FastAPI(title="authsvc")
    app.state.db = db
    app.include_router(recovery.router)
    return app
