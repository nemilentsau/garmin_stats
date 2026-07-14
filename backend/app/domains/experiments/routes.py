"""HTTP routes for experiments and target metrics.

Routes keep FastAPI concerns at the boundary, resolve the app container, and
delegate experiment validation, persistence, exposure, and analysis work to
application use cases.
"""

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
from app.domains.experiments.application.target_metrics import get_target_metrics
from app.domains.experiments.contracts import (
    Experiment,
    ExperimentAnalysis,
    ExperimentAnalysisRefreshResponse,
    ExperimentExposure,
    ExperimentPreviewResponse,
    ExperimentsResponse,
    ExperimentWithAnalysis,
    TargetMetricsResponse,
)

experiments_router = APIRouter(prefix="/api/experiments", tags=["experiments"])
target_metrics_router = APIRouter(prefix="/api/target-metrics", tags=["target-metrics"])


@experiments_router.get("", response_model=ExperimentsResponse)
def get_experiments():
    """Return experiments with their current cached analysis snapshots."""
    container = build_container()
    return list_experiments(
        container.experiments_repo,
        container.experiments_read_source,
    )


# Static paths MUST come before /{experiment_id} to avoid route shadowing.

@experiments_router.post("/preview", response_model=ExperimentPreviewResponse)
def post_preview(experiment: Experiment):
    """Validate an experiment spec and resolved dates without writing it."""
    container = build_container()
    return preview_experiment(
        container.experiments_repo,
        container.experiments_read_source,
        experiment,
    )


@experiments_router.post("/import", response_model=ExperimentWithAnalysis)
def post_import(experiment: Experiment):
    """Validate an experiment spec, persist it, and create initial analysis."""
    container = build_container()
    try:
        return import_experiment(
            container.experiments_repo,
            container.experiments_read_source,
            experiment,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@experiments_router.post(
    "/refresh-analyses",
    response_model=ExperimentAnalysisRefreshResponse,
)
def post_refresh():
    """Refresh cached analyses for active experiments."""
    container = build_container()
    count = refresh_active_experiments(
        container.experiments_repo,
        container.experiments_read_source,
    )
    return ExperimentAnalysisRefreshResponse(refreshed=count)


@experiments_router.post("", response_model=Experiment)
def post_experiment(experiment: Experiment):
    """Create an experiment definition without preview validation or analysis."""
    return create_experiment(build_container().experiments_repo, experiment)


# Dynamic-path routes below.

@experiments_router.get("/{experiment_id}", response_model=ExperimentWithAnalysis)
def get_experiment_detail(experiment_id: str):
    """Return one experiment with its current analysis snapshot."""
    container = build_container()
    try:
        return get_experiment_with_analysis(
            container.experiments_repo,
            container.experiments_read_source,
            experiment_id,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@experiments_router.put("/{experiment_id}", response_model=Experiment)
def put_experiment(experiment_id: str, experiment: Experiment):
    """Replace an existing experiment definition and refresh analysis."""
    container = build_container()
    try:
        return update_experiment(
            container.experiments_repo,
            container.experiments_read_source,
            experiment_id,
            experiment,
        )
    except (LookupError, ValueError) as e:
        status = 404 if isinstance(e, LookupError) else 400
        raise HTTPException(status_code=status, detail=str(e)) from e


@experiments_router.get("/{experiment_id}/analysis", response_model=ExperimentAnalysis | None)
def get_analysis(experiment_id: str):
    """Return the current cached analysis for one experiment."""
    container = build_container()
    try:
        return get_experiment_analysis(
            container.experiments_repo,
            container.experiments_read_source,
            experiment_id,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@experiments_router.get("/{experiment_id}/exposures", response_model=list[ExperimentExposure])
def get_exposures(experiment_id: str):
    """Return recorded exposure rows for one experiment."""
    return list_experiment_exposures(build_container().experiments_repo, experiment_id)


@experiments_router.post("/{experiment_id}/exposures", response_model=ExperimentExposure)
def post_exposure(experiment_id: str, exposure: ExperimentExposure):
    """Persist a manual exposure row and refresh the experiment analysis."""
    container = build_container()
    try:
        return create_experiment_exposure(
            container.experiments_repo,
            container.experiments_read_source,
            experiment_id,
            exposure,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@target_metrics_router.get("", response_model=TargetMetricsResponse)
def list_target_metrics_route():
    """Return the supported experiment target metric registry."""
    return get_target_metrics()
