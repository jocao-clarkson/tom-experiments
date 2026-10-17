from .errors import ValidationError


def require_json_fields(body, spec):
    """spec maps field name -> expected type. Raises ValidationError listing all problems."""
    if not isinstance(body, dict):
        raise ValidationError("request body must be a JSON object")
    problems = {}
    for field, expected in spec.items():
        if field not in body:
            problems[field] = "required"
            continue
        value = body[field]
        if expected is int and isinstance(value, bool):
            problems[field] = "must be int"
        elif not isinstance(value, expected):
            problems[field] = f"must be {expected.__name__}"
    if problems:
        raise ValidationError("invalid request body", details=problems)
    return body


def positive_int(value, field):
    if value <= 0:
        raise ValidationError("invalid request body", details={field: "must be positive"})
    return value
