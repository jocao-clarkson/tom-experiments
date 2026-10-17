from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.api.workouts import WorkoutIn


def test_workout_rejects_negative_duration():
    with pytest.raises(ValidationError):
        WorkoutIn(client_id="abcdefgh", kind="run", started_at=datetime.now(timezone.utc),
                  duration_s=-1, client_updated_at=datetime.now(timezone.utc))


def test_workout_defaults_not_deleted():
    w = WorkoutIn(client_id="abcdefgh", kind="ride", started_at=datetime.now(timezone.utc),
                  duration_s=600, client_updated_at=datetime.now(timezone.utc))
    assert w.deleted is False
