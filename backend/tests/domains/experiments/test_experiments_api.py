"""Experiment API tests."""

import pytest
from fastapi import HTTPException

import app.domains.experiments.api.experiments as experiments_mod
from app.models import Experiment, OutcomeMetric


class TestExperimentApi:
    def test_get_experiment_detail_raises_404_when_missing(self, monkeypatch):
        def _raise(*_args):
            raise LookupError("Experiment exp-1 not found")

        monkeypatch.setattr(experiments_mod, "get_experiment_with_analysis", _raise)

        with pytest.raises(HTTPException) as exc_info:
            experiments_mod.get_experiment_detail("exp-1")
        assert exc_info.value.status_code == 404

    def test_put_experiment_returns_updated_experiment(self, monkeypatch):
        experiment = Experiment(
            id="exp-1",
            name="Meditation",
            outcome_metrics=[OutcomeMetric(path="hrv_nightly")],
        )
        monkeypatch.setattr(experiments_mod, "update_experiment", lambda *_args: experiment)

        result = experiments_mod.put_experiment("exp-1", experiment)

        assert result.id == "exp-1"
