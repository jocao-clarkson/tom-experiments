import json
import logging
from datetime import datetime, timezone

log = logging.getLogger("authsvc.audit")

SENSITIVE_KEYS = {"password", "secret", "token", "recovery_code", "api_key"}


def scrub(data: dict) -> dict:
    """Drop known-sensitive keys (recursively) before anything is persisted."""
    out = {}
    for k, v in data.items():
        if k in SENSITIVE_KEYS:
            continue
        out[k] = scrub(v) if isinstance(v, dict) else v
    return out


class AuditLog:
    def __init__(self, conn):
        self.conn = conn

    def record(self, *, actor: str, action: str, org_id: str, target: str, metadata: dict | None = None) -> None:
        clean = scrub(metadata or {})
        self.conn.execute(
            "INSERT INTO audit_events (at, actor, action, org_id, target, metadata) VALUES (%s, %s, %s, %s, %s, %s)",
            (datetime.now(timezone.utc), actor, action, org_id, target, json.dumps(clean)),
        )
        log.info("audit %s by %s on %s", action, actor, target)
