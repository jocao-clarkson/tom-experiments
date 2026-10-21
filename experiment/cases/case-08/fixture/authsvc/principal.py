from dataclasses import dataclass, field
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, Request

from .cache import TTLMemo
from .settings import Settings, get_settings


@dataclass(frozen=True)
class Principal:
    """Who is making the request. Route handlers authorize against this."""

    subject: str          # user id, or service account id
    org_id: str
    kind: str             # "user" | "service_account"
    role: str | None = None
    scopes: frozenset[str] = field(default_factory=frozenset)

    def require_scope(self, scope: str) -> None:
        if scope not in self.scopes:
            raise HTTPException(status_code=403, detail={"code": "insufficient_scope", "scope": scope})

    def require_org_admin(self, org_id: str) -> None:
        if self.kind != "user" or self.org_id != org_id or self.role != "admin":
            raise HTTPException(status_code=403, detail={"code": "forbidden"})


@lru_cache
def _org_memo() -> TTLMemo:
    return TTLMemo(ttl=get_settings().cache_ttl_seconds, maxsize=4096)


def org_is_active(db, org_id: str) -> bool:
    """True if the org exists and is not suspended."""

    def load() -> bool:
        with db.transaction() as conn:
            row = conn.execute("SELECT suspended_at FROM orgs WHERE id = %s", (org_id,)).fetchone()
        return row is not None and row[0] is None

    return _org_memo().get_or_load(org_id, load)


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value:
        raise HTTPException(status_code=401, detail={"code": "unauthenticated"})
    return value


def current_principal(request: Request, settings: Settings = Depends(get_settings)) -> Principal:
    """Resolve the bearer credential into a Principal. Currently: user JWTs."""
    token = _bearer(request)
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail={"code": "unauthenticated"})
    if not org_is_active(request.app.state.db, claims["org"]):
        raise HTTPException(status_code=401, detail={"code": "unauthenticated"})
    return Principal(
        subject=claims["sub"],
        org_id=claims["org"],
        kind="user",
        role=claims.get("role"),
        scopes=frozenset(claims.get("scopes", [])),
    )
