"""Manual experiment exposure command and treatment-window tests."""

from datetime import date
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import ValidationError

import app.domains.experiments.application.exposures as exposures_mod
import app.domains.experiments.contracts as contracts_mod
from app.domains.experiments.contracts import Experiment, ExperimentDesign


class _Repo:
    def __init__(self, experiment: Experiment | None) -> None:
        self.experiment = experiment
        self.saved = []

    def get_experiment(self, experiment_id: str):
        return self.experiment if self.experiment and self.experiment.id == experiment_id else None

    def save_experiment_exposure(self, exposure) -> None:
        self.saved.append(exposure)


def _experiment() -> Experiment:
    return Experiment(
        id="exp-1",
        name="Meditation",
        design=ExperimentDesign(
            baseline_start_date="2026-06-01",
            baseline_end_date="2026-06-30",
            treatment_start_date="2026-07-01",
            treatment_end_date="2026-07-14",
        ),
    )


def _command(**overrides):
    model = getattr(contracts_mod, "ExperimentExposureCreate", None)
    assert model is not None, "a strict exposure command contract must exist"
    values = {
        "date": "2026-07-10",
        "adherence_state": "full",
        "exposure_score": 1.0,
        "notes": None,
    }
    values.update(overrides)
    return model(**values)


def test_exposure_command_is_strict_and_owns_only_client_authored_fields():
    command = _command()

    assert command.date == date(2026, 7, 10)
    assert "id" not in type(command).model_fields
    assert "experiment_id" not in type(command).model_fields
    with pytest.raises(ValidationError):
        _command(unknown="value")


@pytest.mark.parametrize("score", [-0.01, 1.01])
def test_exposure_score_rejects_values_outside_zero_to_one(score: float):
    with pytest.raises(ValidationError):
        _command(exposure_score=score)


def test_exposure_command_rejects_malformed_date():
    with pytest.raises(ValidationError):
        _command(date="not-a-date")


@pytest.mark.parametrize("candidate", ["2026-06-30", "2026-07-15", "2099-01-01"])
def test_exposure_date_must_be_inside_treatment_and_not_in_future(
    candidate: str, monkeypatch
):
    repo = _Repo(_experiment())
    monkeypatch.setattr(exposures_mod, "persist_experiment_analysis", lambda *_args: None)

    with pytest.raises(ValueError):
        exposures_mod.create_experiment_exposure(
            cast(Any, repo),
            cast(Any, SimpleNamespace()),
            "exp-1",
            _command(date=candidate),
            today=date(2026, 7, 15),
        )

    assert repo.saved == []


def test_valid_exposure_derives_stable_identity_and_persists(monkeypatch):
    repo = _Repo(_experiment())
    monkeypatch.setattr(exposures_mod, "persist_experiment_analysis", lambda *_args: None)

    result = exposures_mod.create_experiment_exposure(
        cast(Any, repo),
        cast(Any, SimpleNamespace()),
        "exp-1",
        _command(),
        today=date(2026, 7, 15),
    )

    assert result.id == "exposure:manual:exp-1:2026-07-10"
    assert result.experiment_id == "exp-1"
    assert result.date == "2026-07-10"
    assert repo.saved == [result]
