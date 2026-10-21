import json
import logging
from datetime import datetime, timezone

from .redact import scrub

log = logging.getLogger("authsvc.audit")


class AuditLog:
    """The one writer for audit_events."""

    def __init__(self, conn):
        self.conn = conn

    def record(self, *, actor: str, action: str, org_id: str, target: str, metadata: dict | None = None) -> None:
        clean = scrub(metadata or {})
        self.conn.execute(
            "INSERT INTO audit_events (at, actor, action, org_id, target, metadata) VALUES (%s, %s, %s, %s, %s, %s)",
            (datetime.now(timezone.utc), actor, action, org_id, target, json.dumps(clean)),
        )
        log.info("audit %s by %s on %s", action, actor, target)
