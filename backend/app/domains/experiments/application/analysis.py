"""Experiment analysis use case orchestration.

This module is the data-loading boundary for analysis computation. It
short-circuits unanalyzable experiments before loading Garmin metrics,
check-ins, or exposures, then delegates pure analysis rules to the domain layer.
"""

from __future__ import annotations

from app.domains.experiments.contracts import Experiment, ExperimentAnalysis
from app.domains.experiments.domain import analysis as domain_analysis

from ..dependencies import ExperimentAnalysisReadSource, ExperimentRepository


def compute_experiment_analysis(
    repo: ExperimentRepository,
    read_source: ExperimentAnalysisReadSource,
    experiment: Experiment,
) -> ExperimentAnalysis:
    """Load repository inputs and compute the current experiment analysis."""
    placeholder = domain_analysis.unanalyzable_placeholder(experiment)
    if placeholder is not None:
        return placeholder
    return domain_analysis.compute_experiment_analysis(
        experiment,
        daily_metrics=read_source.list_daily_metrics(),
        daily_checkins=read_source.list_daily_checkins(),
        exposures=repo.list_experiment_exposures(experiment_id=experiment.id),
    )
