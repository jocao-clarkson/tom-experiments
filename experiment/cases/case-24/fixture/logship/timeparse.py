import re
from datetime import timedelta

_UNITS = {"m": "minutes", "h": "hours", "d": "days", "w": "weeks"}
_PATTERN = re.compile(r"^(\d+)([mhdw])$")


def parse_duration(text: str) -> timedelta:
    """Parse durations like '30m', '12h', '7d', '2w'. Raises ValueError."""
    m = _PATTERN.match(text.strip().lower())
    if not m:
        raise ValueError(f"invalid duration {text!r}; use a number followed by m, h, d or w")
    value = int(m.group(1))
    if value == 0:
        raise ValueError("duration must be greater than zero")
    return timedelta(**{_UNITS[m.group(2)]: value})
