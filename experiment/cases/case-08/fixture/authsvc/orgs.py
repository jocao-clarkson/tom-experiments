from functools import lru_cache

from .cache import TTLMemo
from .settings import get_settings


@lru_cache
def _active_memo() -> TTLMemo:
    return TTLMemo(ttl=get_settings().cache_ttl_seconds, maxsize=4096)


def is_active(db, org_id: str) -> bool:
    """True if the org exists and is not suspended."""

    def load() -> bool:
        with db.transaction() as conn:
            row = conn.execute("SELECT suspended_at FROM orgs WHERE id = %s", (org_id,)).fetchone()
        return row is not None and row[0] is None

    return _active_memo().get_or_load(org_id, load)
