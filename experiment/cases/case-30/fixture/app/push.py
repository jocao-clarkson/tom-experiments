import json

from .serializers import note_to_dict

APNS_MAX_PAYLOAD = 4096


def shared_note_payload(note: dict) -> bytes:
    """Silent push sent to collaborators when a shared note changes, so the
    app can update its local copy without a round trip."""
    body = {"aps": {"content-available": 1}, "note": note_to_dict(note)}
    raw = json.dumps(body, separators=(",", ":")).encode()
    if len(raw) > APNS_MAX_PAYLOAD:
        body["note"] = {"id": note["id"], "updated_at": note["updated_at"]}
        raw = json.dumps(body, separators=(",", ":")).encode()
    return raw
