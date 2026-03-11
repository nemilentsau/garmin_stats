"""Tests for phase 1 foundation routes."""

import pytest
from fastapi import HTTPException

import app.routers.experiments as experiments_mod
import app.routers.profile as profile_mod
import app.routers.routines as routines_mod
from app.models import Experiment, Routine, RoutineEntry, UserProfile


class TestProfileRoutes:
    def test_get_profile_returns_default_profile(self, monkeypatch):
        monkeypatch.setattr(profile_mod, "get_user_profile", lambda: UserProfile())

        profile = profile_mod.get_profile()

        assert profile.id == "default"


class TestRoutineRoutes:
    def test_put_routine_returns_404_when_service_raises_lookup_error(self, monkeypatch):
        monkeypatch.setattr(
            routines_mod,
            "update_routine",
            lambda *_args: (_ for _ in ()).throw(LookupError("Routine routine-1 not found")),
        )

        with pytest.raises(HTTPException, match="Routine routine-1 not found"):
            routines_mod.put_routine(
                "routine-1",
                Routine(id="routine-1", name="Meditation", category="mindfulness"),
            )

    def test_post_entry_returns_400_when_path_and_body_ids_do_not_match(self, monkeypatch):
        monkeypatch.setattr(
            routines_mod,
            "create_routine_entry",
            lambda *_args: (_ for _ in ()).throw(
                ValueError("Routine entry routine_id does not match path id")
            ),
        )

        with pytest.raises(HTTPException, match="Routine entry routine_id does not match path id"):
            routines_mod.post_entry(
                "routine-1",
                RoutineEntry(id="entry-1", routine_id="routine-2", date="2026-01-15"),
            )


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
