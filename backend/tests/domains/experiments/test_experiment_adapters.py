"""Tests for experiment SQLite adapters."""

from app.domains.experiments.adapters import SqliteExperimentRepository
from app.domains.experiments.contracts import (
    Experiment,
    ExperimentExposure,
    ExperimentReport,
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
    report = ExperimentReport(
        id="report-1",
        experiment_id="exp-1",
        report_date="2026-01-16",
        summary="Initial response looks promising.",
    )

    repo.save_experiment(experiment)
    repo.save_experiment_exposure(exposure)
    repo.save_experiment_report(report)

    experiments = repo.list_experiments()
    exposures = repo.list_experiment_exposures(experiment_id="exp-1")
    reports = repo.list_experiment_reports(experiment_id="exp-1")

    assert [item.id for item in experiments] == ["exp-1"]
    assert [item.id for item in exposures] == ["exposure-1"]
    assert [item.id for item in reports] == ["report-1"]
