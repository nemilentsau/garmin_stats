"""Truthfulness and boundary tests for experiment policy controls."""

from inspect import signature

import pytest
from pydantic import ValidationError

from app.domains.experiments.contracts import Experiment, ExperimentDesign, OutcomeMetric
from app.domains.experiments.domain.reporting import classify_confidence


def test_contract_does_not_advertise_unused_effect_or_duplicate_lag_controls():
    assert "min_effect_size" not in OutcomeMetric.model_fields
    assert "expected_lag_days" not in Experiment.model_fields


@pytest.mark.parametrize(
    "values",
    [
        {"expected_lag_days": [-1]},
        {"min_adherence_pct": -0.01},
        {"min_adherence_pct": 1.01},
    ],
)
def test_design_rejects_invalid_policy_boundaries(values):
    with pytest.raises(ValidationError):
        ExperimentDesign(**values)


@pytest.mark.parametrize(
    "payload",
    [
        {"id": "exp", "name": "Experiment", "unknown": True},
        {"id": "exp", "name": "Experiment", "design": {"unknown": True}},
        {
            "id": "exp",
            "name": "Experiment",
            "outcome_metrics": [{"path": "hrv.nightly_avg", "unknown": True}],
        },
    ],
)
def test_authored_experiment_contract_rejects_unknown_fields(payload):
    with pytest.raises(ValidationError):
        Experiment.model_validate(payload)


def test_authored_minimum_adherence_controls_insufficient_confidence_boundary():
    assert "min_adherence_pct" in signature(classify_confidence).parameters

    below = classify_confidence(
        [], [], 0.69, 21, 21, min_adherence_pct=0.70
    )
    at_boundary = classify_confidence(
        [], [], 0.70, 21, 21, min_adherence_pct=0.70
    )

    assert below == "insufficient"
    assert at_boundary == "low"
