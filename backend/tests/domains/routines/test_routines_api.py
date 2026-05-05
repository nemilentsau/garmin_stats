"""Routine API tests."""

import pytest

import app.domains.routines.api.routines as routines_api_mod
from app.models import ScheduleWindow


class TestRoutineApi:
    def test_get_schedule_window_returns_projection(self, monkeypatch):
        monkeypatch.setattr(
            routines_api_mod,
            "get_schedule_window",
            lambda *_args, **_kwargs: ScheduleWindow(
                start_date="2026-03-02", end_date="2026-03-15"
            ),
        )

        window = routines_api_mod.get_routine_schedule_window("2026-03-02")

        assert window.start_date == "2026-03-02"
        assert window.end_date == "2026-03-15"

    def test_get_schedule_window_raises_value_error_for_invalid_date(self, monkeypatch):
        error = ValueError("Invalid isoformat string: 'bad-date'")
        monkeypatch.setattr(
            routines_api_mod,
            "get_schedule_window",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
        )

        with pytest.raises(ValueError, match="Invalid isoformat string: 'bad-date'"):
            routines_api_mod.get_routine_schedule_window("bad-date")

    def test_get_routine_raises_lookup_error_when_missing(self, monkeypatch):
        monkeypatch.setattr(
            routines_api_mod,
            "get_routine",
            lambda *_args: (_ for _ in ()).throw(LookupError("Routine routine-1 not found")),
        )

        with pytest.raises(LookupError, match="Routine routine-1 not found"):
            routines_api_mod.get_routine_detail("routine-1")
