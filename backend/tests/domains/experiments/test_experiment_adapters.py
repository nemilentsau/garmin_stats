"""Tests for experiment SQLite adapters."""

from app.domains.experiments.adapters import SqliteExperimentRepository
from app.domains.experiments.contracts import (
    Experiment,
    ExperimentExposure,
    OutcomeMetric,
)


def test_experiment_family_survives_adapter_round_trip():
    repo = SqliteExperimentRepository()
    experiment = Experiment(
        id="exp-1",
        name="Evening meditation",
        linked_routine_ids=["routine-1"],
        outcome_metrics=[OutcomeMetric(path="hrv_nightly")],
    )
    exposure = ExperimentExposure(
        id="exposure-1",
        experiment_id="exp-1",
        date="2026-01-15",
        exposure_score=1.0,
        adherence_state="full",
    )
    repo.save_experiment(experiment)
    repo.save_experiment_exposure(exposure)

    experiments = repo.list_experiments()
    exposures = repo.list_experiment_exposures(experiment_id="exp-1")

    assert [item.id for item in experiments] == ["exp-1"]
    assert [item.id for item in exposures] == ["exposure-1"]


def test_list_experiments_filters_by_statuses():
    repo = SqliteExperimentRepository()
    repo.save_experiment(
        Experiment(
            id="draft-exp",
            name="Draft meditation",
            status="draft",
            linked_routine_ids=["routine-1"],
            outcome_metrics=[OutcomeMetric(path="hrv_nightly")],
        )
    )
    repo.save_experiment(
        Experiment(
            id="active-exp",
            name="Active meditation",
            status="active",
            linked_routine_ids=["routine-1"],
            outcome_metrics=[OutcomeMetric(path="hrv_nightly")],
        )
    )

    experiments = repo.list_experiments(statuses=("active",))

    assert [item.id for item in experiments] == ["active-exp"]
