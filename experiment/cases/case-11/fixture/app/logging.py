"""Structured logging. All service code logs through log_event."""
import json
import logging

_logger = logging.getLogger("orders")

REDACTED_KEYS = {"card_last4", "billing_address", "email", "phone", "authorization", "card_fingerprint"}


def _redact(value):
    if isinstance(value, dict):
        return {k: ("[redacted]" if k in REDACTED_KEYS else _redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def log_event(event: str, level: int = logging.INFO, **fields) -> None:
    _logger.log(level, json.dumps({"event": event, **_redact(fields)}, default=str))
