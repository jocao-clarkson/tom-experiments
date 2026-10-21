import os

from . import create_app
from .http_client import ResilientClient
from .repository import OrderRepository

DEFAULTS = {
    "ORDERS_DB_PATH": "orders.db",
    "PAYFAST_BASE_URL": "https://api.payfast.example",
    "PAYFAST_TIMEOUT": 4.0,
    "PAYFAST_MAX_RETRIES": 2,
    "PAYFAST_BACKOFF": 0.25,
}


def load_settings(environ=None):
    environ = os.environ if environ is None else environ
    settings = dict(DEFAULTS)
    for key, default in DEFAULTS.items():
        if key in environ:
            settings[key] = type(default)(environ[key])
    settings["PAYFAST_API_KEY"] = environ.get("PAYFAST_API_KEY", "")
    return settings


def build_payments_client(settings, session=None):
    return ResilientClient(
        settings["PAYFAST_BASE_URL"],
        settings["PAYFAST_API_KEY"],
        timeout=settings["PAYFAST_TIMEOUT"],
        max_retries=settings["PAYFAST_MAX_RETRIES"],
        backoff_base=settings["PAYFAST_BACKOFF"],
        session=session,
    )


def build_app(environ=None):
    settings = load_settings(environ)
    repo = OrderRepository(settings["ORDERS_DB_PATH"])
    return create_app(repo, build_payments_client(settings), settings)
