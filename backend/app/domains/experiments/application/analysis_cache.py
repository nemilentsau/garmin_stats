"""Cached experiment analysis read-model use cases."""

from __future__ import annotations

import logging
from datetime import date as date_type

from app.models import Experiment, ExperimentAnalysis

from .analysis import (
    compute_experiment_analysis,
    current_treatment_window_end,
    expected_experiment_phase,
)
from .ports import ExperimentRepository

log = logging.getLogger(__name__)


def persist_experiment_analysis(
    repo: ExperimentRepository,
    experiment: Experiment,
) -> ExperimentAnalysis | None:
    """Refresh the saved analysis so reads stay aligned with the experiment spec."""
    if experiment.design is None:
        repo.delete_experiment_analysis(experiment.id)
        return None

    analysis = compute_experiment_analysis(repo, experiment)
    repo.save_experiment_analysis(experiment.id, analysis)
    return analysis


def analysis_needs_refresh(
    experiment: Experiment,
    analysis: ExperimentAnalysis | None,
) -> bool:
    if experiment.design is None:
        return analysis is not None
    if analysis is None:
        return False

    if analysis.analysis_date != date_type.today().isoformat():
        return True
    if analysis.phase != expected_experiment_phase(experiment):
        return True

    treatment_start = experiment.design.treatment_start_date
    treatment_end = current_treatment_window_end(experiment.design)
    if treatment_start is None or treatment_end is None or treatment_end < treatment_start:
        return False

    if not analysis.adherence_by_day:
        return True
    return analysis.adherence_by_day[-1].date < treatment_end


def refresh_if_stale(
    repo: ExperimentRepository,
    experiment: Experiment,
    analysis: ExperimentAnalysis | None,
) -> ExperimentAnalysis | None:
    if analysis_needs_refresh(experiment, analysis):
        return persist_experiment_analysis(repo, experiment)
    return analysis


def load_current_analysis(
    repo: ExperimentRepository,
    experiment: Experiment,
) -> ExperimentAnalysis | None:
    return refresh_if_stale(repo, experiment, repo.get_experiment_analysis(experiment.id))


def get_experiment_analysis(
    repo: ExperimentRepository,
    experiment_id: str,
) -> ExperimentAnalysis | None:
    """Return current analysis for an experiment, refreshing stale cached rows."""
    experiment = repo.get_experiment(experiment_id)
    if experiment is None:
        raise LookupError(f"Experiment {experiment_id} not found")
    return load_current_analysis(repo, experiment)


def refresh_active_experiments(repo: ExperimentRepository) -> int:
    """Recompute analysis for all active experiments. Returns count refreshed."""
    experiments = repo.list_experiments(status="active")
    count = 0
    for experiment in experiments:
        if experiment.design is None:
            continue
        try:
            analysis = compute_experiment_analysis(repo, experiment)
            repo.save_experiment_analysis(experiment.id, analysis)
            count += 1
        except Exception:
            log.exception("Failed to refresh experiment %s", experiment.id)
    return count
