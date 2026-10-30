from datetime import timedelta

import pytest

from logship.timeparse import parse_duration


@pytest.mark.parametrize("text,expected", [
    ("30m", timedelta(minutes=30)),
    ("12h", timedelta(hours=12)),
    ("7d", timedelta(days=7)),
    ("2W", timedelta(weeks=2)),
])
def test_parse(text, expected):
    assert parse_duration(text) == expected


@pytest.mark.parametrize("text", ["", "7", "d7", "1.5d", "0d", "-3d", "7y"])
def test_reject(text):
    with pytest.raises(ValueError):
        parse_duration(text)
