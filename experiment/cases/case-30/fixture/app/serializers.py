import json


def note_to_dict(note: dict) -> dict:
    """Canonical JSON form of a note. Used by GET /notes/{id}, GET /sync and
    the push payload builder."""
    out = {
        "id": note["id"],
        "title": note["title"],
        "body": note["body"],
        "updated_at": note["updated_at"],
    }
    if note.get("reminders"):
        out["reminders"] = json.loads(note["reminders"])
    return out
