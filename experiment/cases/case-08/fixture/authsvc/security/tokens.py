import secrets
import string

_BASE62 = string.ascii_letters + string.digits


def random_base62(length: int) -> str:
    return "".join(secrets.choice(_BASE62) for _ in range(length))


def recovery_code() -> str:
    """Ten-character code shown once to the user, grouped for readability."""
    raw = random_base62(10).lower()
    return f"{raw[:5]}-{raw[5:]}"
