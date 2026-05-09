"""Routine API tests."""

import app.domains.routines.routes as routines_api_mod
from app.domains.routines.contracts import ScheduleWindow


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
