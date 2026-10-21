"""Redaction shared by the audit log and request logging."""

_SENSITIVE_SUFFIXES = ("password", "secret", "token", "_key", "_code")


def is_sensitive(field: str) -> bool:
    return field.lower().endswith(_SENSITIVE_SUFFIXES)


def scrub(data: dict) -> dict:
    """Drop sensitive fields (recursively) before anything is persisted."""
    out = {}
    for k, v in data.items():
        if is_sensitive(k):
            continue
        out[k] = scrub(v) if isinstance(v, dict) else v
    return out


def mask_bearer(header: str) -> str:
    """Keep the JWT header and claims for debugging; replace the signature."""
    head, dot, _signature = header.rpartition(".")
    return f"{head}{dot}<redacted>" if dot else header
