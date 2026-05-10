"""Experiment analysis use case orchestration."""

from __future__ import annotations

from app.domains.experiments.contracts import Experiment, ExperimentAnalysis
from app.domains.experiments.domain.analysis import (
    compute_experiment_analysis as compute_domain_experiment_analysis,
)

from ..dependencies import ExperimentRepository


def compute_experiment_analysis(
    repo: ExperimentRepository,
    experiment: Experiment,
) -> ExperimentAnalysis:
    """Load analysis inputs and compute the current experiment analysis."""
    return compute_domain_experiment_analysis(
        experiment,
        daily_metrics=repo.list_daily_metrics(),
        daily_checkins=repo.list_daily_checkins(),
        exposures=repo.list_experiment_exposures(experiment_id=experiment.id),
    )
