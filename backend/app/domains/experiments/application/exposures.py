"""Manual experiment exposure use cases.

Exposure rows are user-authored experiment-day records. Saving one immediately
refreshes the cached analysis for the owning experiment.
"""

from __future__ import annotations

import logging
from datetime import date

from app.domains.experiments.contracts import (
    ExperimentExposure,
    ExperimentExposureCreate,
)

from ..dependencies import ExperimentAnalysisReadSource, ExperimentRepository
from .analysis_cache import persist_experiment_analysis

log = logging.getLogger(__name__)


def list_experiment_exposures(
    repo: ExperimentRepository,
    experiment_id: str,
) -> list[ExperimentExposure]:
    """Return recorded exposure rows for one experiment."""
    if not repo.experiment_exists(experiment_id):
        raise LookupError(f"Experiment {experiment_id} not found")
    return repo.list_experiment_exposures(experiment_id=experiment_id)


def create_experiment_exposure(
    repo: ExperimentRepository,
    read_source: ExperimentAnalysisReadSource,
    experiment_id: str,
    command: ExperimentExposureCreate,
    *,
    today: date | None = None,
) -> ExperimentExposure:
    """Persist a manual exposure row and refresh cached analysis."""
    experiment = repo.get_experiment(experiment_id)
    if experiment is None:
        raise LookupError(f"Experiment {experiment_id} not found")

    design = experiment.design
    if design is None or design.treatment_start_date is None:
        raise ValueError("Experiment has no treatment window")

    exposure_date = command.date
    current_day = today or date.today()
    treatment_start = date.fromisoformat(design.treatment_start_date)
    treatment_end = (
        date.fromisoformat(design.treatment_end_date)
        if design.treatment_end_date is not None
        else current_day
    )
    if exposure_date > current_day:
        raise ValueError("Exposure date cannot be in the future")
    if exposure_date < treatment_start:
        raise ValueError("Exposure date cannot be before treatment start")
    if exposure_date > treatment_end:
        raise ValueError("Exposure date cannot be after treatment end")

    date_str = exposure_date.isoformat()
    exposure = ExperimentExposure(
        id=f"exposure:manual:{experiment_id}:{date_str}",
        experiment_id=experiment_id,
        date=date_str,
        exposure_score=command.exposure_score,
        adherence_state=command.adherence_state,
        notes=command.notes,
    )

    repo.save_experiment_exposure_and_invalidate_analysis(exposure)
    try:
        persist_experiment_analysis(repo, read_source, experiment)
    except Exception:
        log.exception(
            "Exposure %s was saved but experiment analysis refresh failed",
            exposure.id,
        )
    return exposure
