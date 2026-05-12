"""Cached experiment analysis read-model use cases.

Experiment analysis is stored as a read model so list/detail endpoints can stay
cheap. These helpers decide when cached snapshots are stale, recompute them
through the analysis use case, and avoid redundant writes when content has not
changed.
"""

from __future__ import annotations

import logging
from datetime import date as date_type

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


def _analysis_unchanged(cached: ExperimentAnalysis, fresh: ExperimentAnalysis) -> bool:
    """Return whether the cached analysis already matches the fresh snapshot."""
    return cached == fresh


def persist_experiment_analysis(
    repo: ExperimentRepository,
    experiment: Experiment,
    *,
    cached: ExperimentAnalysis | None = None,
) -> ExperimentAnalysis | None:
    """Compute and save the analysis snapshot unless cached content matches."""
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
    """Return whether a cached analysis should be recomputed on read."""
    if experiment.design is None:
        return analysis is not None
    if analysis is None:
        return False

    if analysis.phase != expected_experiment_phase(experiment):
        return True

    # Daily safety net: catches data drift (e.g. late checkin save, manual
    # re-ingest) that no other refresh path notices.
    if analysis.analysis_date != date_type.today().isoformat():
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
    """Return a fresh analysis when the cached snapshot is stale."""
    if analysis_needs_refresh(experiment, analysis):
        return persist_experiment_analysis(repo, experiment, cached=analysis)
    return analysis


def load_current_analysis(
    repo: ExperimentRepository,
    experiment: Experiment,
) -> ExperimentAnalysis | None:
    """Load one cached analysis and refresh it when read-time policy requires."""
    return refresh_if_stale(repo, experiment, repo.get_experiment_analysis(experiment.id))


def get_experiment_analysis(
    repo: ExperimentRepository,
    experiment_id: str,
) -> ExperimentAnalysis | None:
    """Return current analysis for an experiment id."""
    experiment = repo.get_experiment(experiment_id)
    if experiment is None:
        raise LookupError(f"Experiment {experiment_id} not found")
    return load_current_analysis(repo, experiment)


def refresh_active_experiment_analyses(
    repo: ExperimentRepository,
) -> dict[str, ExperimentAnalysis]:
    """Return current active analyses, refreshing only missing or stale snapshots.

    Bulk callers (scan/list views) use this path so missing active analyses are
    materialized for scan results while fresh cached snapshots avoid data loads
    and writes. Experiments without a design are skipped; per-experiment
    failures are logged and excluded.
    """
    experiments = repo.list_experiments(statuses=("active",))
    cached_analyses = repo.list_all_experiment_analyses()
    refreshed: dict[str, ExperimentAnalysis] = {}
    for experiment in experiments:
        if experiment.design is None:
            continue
        cached = cached_analyses.get(experiment.id)
        if cached is not None and not analysis_needs_refresh(experiment, cached):
            refreshed[experiment.id] = cached
            continue
        try:
            analysis = persist_experiment_analysis(
                repo, experiment, cached=cached,
            )
        except Exception:
            log.exception("Failed to refresh experiment %s", experiment.id)
            continue
        if analysis is not None:
            refreshed[experiment.id] = analysis
    return refreshed


def refresh_active_experiments(repo: ExperimentRepository) -> int:
    """Recompute analyses for active experiments and return attempted count."""
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
