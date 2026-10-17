from datetime import date

from etl.config import JobConfig
from etl.jobs import daily_sessions


def cfg(lookback=1):
    return JobConfig("b", "dsn", lookback, run_date=date(2024, 6, 11))


def ev(i, user, platform="ios", type_="session_start"):
    return {"event_id": f"e{i}", "type": type_, "user_id": user, "platform": platform}


def rows(wh):
    return wh.conn.execute("SELECT * FROM sessions_daily ORDER BY day, platform").fetchall()


def test_counts_and_dedupes(storage, write_events, warehouse):
    write_events("2024-06-10", [ev(1, "u1"), ev(1, "u1"), ev(2, "u1"), ev(3, "u2", "android")])
    assert daily_sessions.run(cfg(), storage, warehouse)
    assert rows(warehouse) == [("2024-06-10", "android", 1, 1), ("2024-06-10", "ios", 2, 1)]


def test_rerun_is_idempotent(storage, write_events, warehouse):
    write_events("2024-06-10", [ev(1, "u1")])
    daily_sessions.run(cfg(), storage, warehouse)
    daily_sessions.run(cfg(), storage, warehouse)
    assert rows(warehouse) == [("2024-06-10", "ios", 1, 1)]


def test_too_many_malformed_keeps_previous_partition(storage, write_events, warehouse):
    write_events("2024-06-10", [ev(1, "u1")])
    daily_sessions.run(cfg(), storage, warehouse)
    write_events("2024-06-10", [], name="part-1", raw_lines=["{not json"] * 5)
    assert daily_sessions.run(cfg(), storage, warehouse) is False
    assert rows(warehouse) == [("2024-06-10", "ios", 1, 1)]
