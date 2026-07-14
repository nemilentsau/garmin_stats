"""Manual experiment exposure use cases.

Exposure rows are user-authored experiment-day records. Saving one immediately
refreshes the cached analysis for the owning experiment.
"""

from __future__ import annotations

from app.domains.experiments.contracts import ExperimentExposure

from ..dependencies import ExperimentAnalysisReadSource, ExperimentRepository
from .analysis_cache import persist_experiment_analysis


def list_experiment_exposures(
    repo: ExperimentRepository,
    experiment_id: str,
) -> list[ExperimentExposure]:
    """Return recorded exposure rows for one experiment."""
    return repo.list_experiment_exposures(experiment_id=experiment_id)


def create_experiment_exposure(
    repo: ExperimentRepository,
    read_source: ExperimentAnalysisReadSource,
    experiment_id: str,
    exposure: ExperimentExposure,
) -> ExperimentExposure:
    """Persist a manual exposure row and refresh cached analysis."""
    if exposure.experiment_id != experiment_id:
        raise ValueError("Exposure experiment_id mismatch")

    experiment = repo.get_experiment(experiment_id)
    if experiment is None:
        raise LookupError(f"Experiment {experiment_id} not found")

    repo.save_experiment_exposure(exposure)
    persist_experiment_analysis(repo, read_source, experiment)
    return exposure
