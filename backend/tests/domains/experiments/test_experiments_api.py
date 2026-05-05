"""Experiment API tests."""

import pytest
from fastapi import HTTPException

import app.domains.experiments.api.experiments as experiments_mod
from app.models import Experiment, OutcomeMetric


def _experiment() -> Experiment:
    return Experiment(
        id="exp-1",
        name="Meditation",
        outcome_metrics=[OutcomeMetric(path="hrv_nightly")],
    )


class TestExperimentApi:
    def test_get_experiment_detail_raises_404_when_missing(self, monkeypatch):
        monkeypatch.setattr(
            experiments_mod,
            "get_experiment_with_analysis",
            lambda *_args: (_ for _ in ()).throw(LookupError("Experiment exp-1 not found")),
        )

        with pytest.raises(HTTPException) as exc_info:
            experiments_mod.get_experiment_detail("exp-1")
        assert exc_info.value.status_code == 404

    def test_put_experiment_returns_updated_experiment(self, monkeypatch):
        experiment = _experiment()
        monkeypatch.setattr(experiments_mod, "update_experiment", lambda *_args: experiment)

        result = experiments_mod.put_experiment("exp-1", experiment)

        assert result.id == "exp-1"

    def test_put_experiment_raises_404_when_missing(self, monkeypatch):
        monkeypatch.setattr(
            experiments_mod,
            "update_experiment",
            lambda *_args: (_ for _ in ()).throw(LookupError("Experiment exp-1 not found")),
        )

        with pytest.raises(HTTPException) as exc_info:
            experiments_mod.put_experiment("exp-1", _experiment())
        assert exc_info.value.status_code == 404

    def test_put_experiment_raises_400_on_invalid_payload(self, monkeypatch):
        monkeypatch.setattr(
            experiments_mod,
            "update_experiment",
            lambda *_args: (_ for _ in ()).throw(ValueError("outcome_metrics must be non-empty")),
        )

        with pytest.raises(HTTPException) as exc_info:
            experiments_mod.put_experiment("exp-1", _experiment())
        assert exc_info.value.status_code == 400
