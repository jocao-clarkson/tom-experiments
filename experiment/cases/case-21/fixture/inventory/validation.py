from typing import Any

from .errors import ValidationFailed


def validate_payload(payload: Any, schema: dict) -> dict:
    """Validate a JSON body against a minimal schema.

    schema maps field name -> dict(type=..., required=bool, min=..., max=...).
    Unknown fields are rejected. Returns the cleaned payload.
    """
    if not isinstance(payload, dict):
        raise ValidationFailed("body must be a JSON object")
    unknown = set(payload) - set(schema)
    if unknown:
        raise ValidationFailed("unknown fields", fields=sorted(unknown))
    cleaned = {}
    for name, rule in schema.items():
        if name not in payload:
            if rule.get("required", False):
                raise ValidationFailed(f"{name} is required", field=name)
            if "default" in rule:
                cleaned[name] = rule["default"]
            continue
        value = payload[name]
        expected = rule["type"]
        if (expected is int and isinstance(value, bool)) or not isinstance(value, expected):
            raise ValidationFailed(f"{name} must be {expected.__name__}", field=name)
        if "min" in rule and value < rule["min"]:
            raise ValidationFailed(f"{name} must be >= {rule['min']}", field=name)
        if "max" in rule and value > rule["max"]:
            raise ValidationFailed(f"{name} must be <= {rule['max']}", field=name)
        cleaned[name] = value
    return cleaned
