"""Experiment API tests."""

import pytest
from fastapi import HTTPException

import app.domains.experiments.routes as experiments_mod
from app.domains.experiments.contracts import (
    Experiment,
    OutcomeMetric,
)
from app.main import app


def _experiment() -> Experiment:
    return Experiment(
        id="exp-1",
        name="Meditation",
        outcome_metrics=[OutcomeMetric(path="hrv_nightly")],
    )


class TestExperimentApi:
    def test_experiment_content_can_only_enter_through_preview_and_import(self):
        paths = app.openapi()["paths"]

        assert "post" not in paths["/api/experiments"]
        assert "put" not in paths["/api/experiments/{experiment_id}"]
        assert "post" in paths["/api/experiments/preview"]
        assert "post" in paths["/api/experiments/import"]

    def test_get_experiment_detail_raises_404_when_missing(self, monkeypatch):
        monkeypatch.setattr(
            experiments_mod,
            "get_experiment_with_analysis",
            lambda *_args: (_ for _ in ()).throw(LookupError("Experiment exp-1 not found")),
        )

        with pytest.raises(HTTPException) as exc_info:
            experiments_mod.get_experiment_detail("exp-1")
        assert exc_info.value.status_code == 404
