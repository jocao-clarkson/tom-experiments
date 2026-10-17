from datetime import datetime

from etl.sessionize import sessionize


def ev(visitor, minute, url="/"):
    return {"visitor_id": visitor, "ts": datetime(2026, 10, 1, 12, minute), "url": url}


def test_gap_splits_sessions():
    sessions = sessionize([ev("v1", 0), ev("v1", 10), ev("v1", 50)], gap_minutes=30)
    assert [s["pageviews"] for s in sessions] == [2, 1]


def test_visitors_are_separate():
    sessions = sessionize([ev("a", 0), ev("b", 1)], gap_minutes=30)
    assert {s["visitor_id"] for s in sessions} == {"a", "b"}
