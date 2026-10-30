from dataclasses import dataclass

from fastapi import Header, HTTPException


@dataclass(frozen=True)
class CurrentUser:
    id: str


def current_user(x_user_id: str | None = Header(default=None)) -> CurrentUser:
    """The edge proxy validates the session and forwards X-User-ID."""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="unauthenticated")
    return CurrentUser(id=x_user_id)
