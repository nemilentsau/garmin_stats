"""Manual experiment exposure use cases.

Manual exposure rows are user-authored overrides or corrections. Saving one
immediately refreshes the cached analysis for the owning experiment so reads
reflect the override.
"""

from __future__ import annotations

from app.domains.experiments.contracts import ExperimentExposure

from ..dependencies import ExperimentRepository
from .analysis_cache import persist_experiment_analysis


def list_experiment_exposures(
    repo: ExperimentRepository,
    experiment_id: str,
) -> list[ExperimentExposure]:
    """Return manual and derived exposure rows for one experiment."""
    return repo.list_experiment_exposures(experiment_id=experiment_id)


def create_experiment_exposure(
    repo: ExperimentRepository,
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
    persist_experiment_analysis(repo, experiment)
    return exposure
