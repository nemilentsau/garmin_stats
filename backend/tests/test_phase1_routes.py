"""Tests for phase 1 foundation routes."""

import pytest
from fastapi import HTTPException

import app.domains.experiments.api.experiments as experiments_mod
import app.domains.routines.api.routines as routines_api_mod
import app.routers.profile as profile_mod
import app.routers.routines as routines_mod
from app.models import (
    Experiment,
    OutcomeMetric,
    ScheduleWindow,
    UserProfile,
)


class TestProfileRoutes:
    def test_get_profile_returns_default_profile(self, monkeypatch):
        monkeypatch.setattr(profile_mod, "get_user_profile", lambda: UserProfile())

        profile = profile_mod.get_profile()

        assert profile.id == "default"


class TestRoutineRoutes:
    def test_get_schedule_window_returns_projection(self, monkeypatch):
        monkeypatch.setattr(
            routines_mod,
            "get_schedule_window",
            lambda start_date: ScheduleWindow(start_date=start_date, end_date="2026-03-15"),
        )

        window = routines_mod.get_schedule_window("2026-03-02")

        assert window.start_date == "2026-03-02"
        assert window.end_date == "2026-03-15"

    def test_get_schedule_window_raises_value_error_for_invalid_date(self, monkeypatch):
        error = ValueError("Invalid isoformat string: 'bad-date'")
        monkeypatch.setattr(
            routines_mod,
            "get_schedule_window",
            lambda *_args: (_ for _ in ()).throw(error),
        )

        with pytest.raises(ValueError, match="Invalid isoformat string: 'bad-date'"):
            routines_mod.get_schedule_window("bad-date")

    def test_get_routine_raises_lookup_error_when_missing(self, monkeypatch):
        monkeypatch.setattr(
            routines_api_mod,
            "get_routine",
            lambda *_args: (_ for _ in ()).throw(LookupError("Routine routine-1 not found")),
        )

        with pytest.raises(LookupError, match="Routine routine-1 not found"):
            routines_api_mod.get_routine_detail("routine-1")


class TestExperimentRoutes:
    def test_get_experiment_detail_raises_404_when_missing(self, monkeypatch):
        def _raise(*_args):
            raise LookupError("Experiment exp-1 not found")

        monkeypatch.setattr(experiments_mod, "get_experiment_with_analysis", _raise)

        with pytest.raises(HTTPException) as exc_info:
            experiments_mod.get_experiment_detail("exp-1")
        assert exc_info.value.status_code == 404

    def test_put_experiment_returns_updated_experiment(self, monkeypatch):
        experiment = Experiment(
            id="exp-1", name="Meditation",
            outcome_metrics=[OutcomeMetric(path="hrv_nightly")],
        )
        monkeypatch.setattr(experiments_mod, "update_experiment", lambda *_args: experiment)

        result = experiments_mod.put_experiment("exp-1", experiment)

        assert result.id == "exp-1"
