"""Tests for phase 1 foundation routes."""

import pytest
from fastapi import HTTPException

import app.routers.experiments as experiments_mod
import app.routers.profile as profile_mod
import app.routers.routines as routines_mod
from app.models import Experiment, UserProfile


class TestProfileRoutes:
    def test_get_profile_returns_default_profile(self, monkeypatch):
        monkeypatch.setattr(profile_mod, "get_user_profile", lambda: UserProfile())

        profile = profile_mod.get_profile()

        assert profile.id == "default"


class TestRoutineRoutes:
    def test_get_routine_detail_returns_404_when_service_raises_lookup_error(self, monkeypatch):
        monkeypatch.setattr(
            routines_mod,
            "get_routine",
            lambda *_args: (_ for _ in ()).throw(LookupError("Routine routine-1 not found")),
        )

        with pytest.raises(HTTPException, match="Routine routine-1 not found"):
            routines_mod.get_routine_detail("routine-1")


class TestExperimentRoutes:
    def test_get_experiment_detail_returns_404_when_missing(self, monkeypatch):
        monkeypatch.setattr(
            experiments_mod,
            "get_experiment",
            lambda *_args: (_ for _ in ()).throw(LookupError("Experiment exp-1 not found")),
        )

        with pytest.raises(HTTPException, match="Experiment exp-1 not found"):
            experiments_mod.get_experiment_detail("exp-1")

    def test_put_experiment_returns_updated_experiment(self, monkeypatch):
        experiment = Experiment(id="exp-1", name="Meditation", outcome_metrics=["hrv_nightly"])
        monkeypatch.setattr(experiments_mod, "update_experiment", lambda *_args: experiment)

        result = experiments_mod.put_experiment("exp-1", experiment)

        assert result.id == "exp-1"
