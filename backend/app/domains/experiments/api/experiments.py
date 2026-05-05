"""Experiment HTTP routes."""

from fastapi import APIRouter, HTTPException

from app.bootstrap.container import build_container
from app.domains.experiments.application.analysis_cache import (
    get_experiment_analysis,
    refresh_active_experiments,
)
from app.domains.experiments.application.exposures import (
    create_experiment_exposure,
    list_experiment_exposures,
)
from app.domains.experiments.application.management import (
    create_experiment,
    get_experiment_with_analysis,
    import_experiment,
    list_experiments,
    update_experiment,
)
from app.domains.experiments.application.preview import preview_experiment
from app.models import (
    Experiment,
    ExperimentAnalysis,
    ExperimentAnalysisRefreshResponse,
    ExperimentExposure,
    ExperimentPreviewResponse,
    ExperimentsResponse,
    ExperimentWithAnalysis,
)

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


@router.get("", response_model=ExperimentsResponse)
def get_experiments():
    """Return all experiments with latest analysis."""
    return list_experiments(build_container().experiments_repo)


# Static paths MUST come before /{experiment_id} to avoid route shadowing.

@router.post("/preview", response_model=ExperimentPreviewResponse)
def post_preview(experiment: Experiment):
    """Validate an experiment spec without persisting."""
    container = build_container()
    return preview_experiment(
        container.experiments_repo,
        experiment,
        routine_repo=container.routines_repo,
    )


@router.post("/import", response_model=ExperimentWithAnalysis)
def post_import(experiment: Experiment):
    """Validate, persist, and run initial analysis."""
    container = build_container()
    try:
        return import_experiment(
            container.experiments_repo,
            experiment,
            routine_repo=container.routines_repo,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/refresh-analyses", response_model=ExperimentAnalysisRefreshResponse)
def post_refresh():
    """Recompute analyses for all active experiments."""
    count = refresh_active_experiments(build_container().experiments_repo)
    return ExperimentAnalysisRefreshResponse(refreshed=count)


@router.post("", response_model=Experiment)
def post_experiment(experiment: Experiment):
    """Create an experiment (simple CRUD, no analysis)."""
    return create_experiment(build_container().experiments_repo, experiment)


# Dynamic-path routes below.

@router.get("/{experiment_id}", response_model=ExperimentWithAnalysis)
def get_experiment_detail(experiment_id: str):
    """Return a single experiment with analysis."""
    try:
        return get_experiment_with_analysis(build_container().experiments_repo, experiment_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/{experiment_id}", response_model=Experiment)
def put_experiment(experiment_id: str, experiment: Experiment):
    """Replace an existing experiment."""
    try:
        return update_experiment(build_container().experiments_repo, experiment_id, experiment)
    except (LookupError, ValueError) as e:
        status = 404 if isinstance(e, LookupError) else 400
        raise HTTPException(status_code=status, detail=str(e)) from e


@router.get("/{experiment_id}/analysis", response_model=ExperimentAnalysis | None)
def get_analysis(experiment_id: str):
    """Return the latest computed analysis for an experiment."""
    try:
        return get_experiment_analysis(build_container().experiments_repo, experiment_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{experiment_id}/exposures", response_model=list[ExperimentExposure])
def get_exposures(experiment_id: str):
    """Return all exposures for an experiment."""
    return list_experiment_exposures(build_container().experiments_repo, experiment_id)


@router.post("/{experiment_id}/exposures", response_model=ExperimentExposure)
def post_exposure(experiment_id: str, exposure: ExperimentExposure):
    """Log an exposure entry for an experiment."""
    try:
        return create_experiment_exposure(
            build_container().experiments_repo,
            experiment_id,
            exposure,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
