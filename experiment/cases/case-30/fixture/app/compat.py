from fastapi import Request


def client_version(request: Request) -> tuple[int, int]:
    """Parse X-App-Version ("4.2.1" -> (4, 2)). Unknown or missing -> (0, 0)."""
    raw = request.headers.get("x-app-version", "")
    parts = raw.split(".")
    try:
        return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        return 0, 0


# Response keys that older app builds cannot decode, with the first version
# that understands them. Older Android builds use a strict decoder that fails
# on unknown keys.
GATED_KEYS: dict[str, tuple[int, int]] = {
    "reminders": (3, 6),
}


def shape_for_client(payload: dict, version: tuple[int, int]) -> dict:
    """Drop keys the calling client is too old to understand. Routes call this
    on every note they return; serializers stay version-agnostic."""
    return {k: v for k, v in payload.items() if k not in GATED_KEYS or version >= GATED_KEYS[k]}
