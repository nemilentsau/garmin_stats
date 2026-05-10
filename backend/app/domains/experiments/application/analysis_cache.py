"""Cached experiment analysis read-model use cases."""

from __future__ import annotations

import logging

from app.domains.experiments.contracts import (
    Experiment,
    ExperimentAnalysis,
)
from app.domains.experiments.domain.analysis import (
    current_treatment_window_end,
    expected_experiment_phase,
)

from ..dependencies import ExperimentRepository
from .analysis import compute_experiment_analysis

log = logging.getLogger(__name__)


_VOLATILE_ANALYSIS_FIELDS = {"analysis_date"}


def _analysis_unchanged(cached: ExperimentAnalysis, fresh: ExperimentAnalysis) -> bool:
    """True when nothing meaningful changed.

    ``analysis_date`` is excluded so a daily recompute that produces identical
    content does not trigger a write.
    """
    return cached.model_dump(exclude=_VOLATILE_ANALYSIS_FIELDS) == fresh.model_dump(
        exclude=_VOLATILE_ANALYSIS_FIELDS,
    )


def persist_experiment_analysis(
    repo: ExperimentRepository,
    experiment: Experiment,
    *,
    cached: ExperimentAnalysis | None = None,
) -> ExperimentAnalysis | None:
    """Refresh the saved analysis so reads stay aligned with the experiment spec."""
    if experiment.design is None:
        repo.delete_experiment_analysis(experiment.id)
        return None

    fresh = compute_experiment_analysis(repo, experiment)
    existing = cached if cached is not None else repo.get_experiment_analysis(experiment.id)
    if existing is not None and _analysis_unchanged(existing, fresh):
        return existing
    repo.save_experiment_analysis(experiment.id, fresh)
    return fresh


def analysis_needs_refresh(
    experiment: Experiment,
    analysis: ExperimentAnalysis | None,
) -> bool:
    if experiment.design is None:
        return analysis is not None
    if analysis is None:
        return False

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
        return persist_experiment_analysis(repo, experiment, cached=analysis)
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
    experiments = repo.list_experiments(statuses=("active",))
    cached_analyses = repo.list_all_experiment_analyses()
    count = 0
    for experiment in experiments:
        if experiment.design is None:
            continue
        try:
            persist_experiment_analysis(
                repo, experiment, cached=cached_analyses.get(experiment.id),
            )
            count += 1
        except Exception:
            log.exception("Failed to refresh experiment %s", experiment.id)
    return count
