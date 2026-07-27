"""HTTP routes for v3 package import, Today/schedule views, and capture logs.

Routes bind FastAPI request/response metadata to the training application use
cases (`application/imports.py`, `application/read_models.py`). They resolve
the repository from the app container and leave artifact validation,
schedule compilation, display projection, and capture-log persistence to
those modules — this file has no policy of its own beyond the LookupError ->
404 fallback for "no active block", handled by the app-level exception
handler registered in `bootstrap/app.py`.
"""

from datetime import date as Date
from typing import Annotated

from fastapi import APIRouter, Query

from app.bootstrap.container import build_container
from app.contracts.errors import error_responses
from app.domains.training.application.import_packages import (
    ImportPackageRequest,
    import_package,
)
from app.domains.training.application.imports import ImportResult
from app.domains.training.application.read_models import (
    TrainingLogUpdateRequest,
    get_block_status,
    get_training_schedule_window,
    get_training_today,
    upsert_training_log,
)
from app.domains.training.contracts import (
    TrainingBlockStatus,
    TrainingCardLog,
    TrainingScheduleWindow,
    TrainingTodayResponse,
)

training_router = APIRouter(prefix="/api/training", tags=["training"])
_TodayDate = Annotated[Date, Query(description="Date (YYYY-MM-DD)")]
_ScheduleStartDate = Annotated[Date, Query(description="Start date (YYYY-MM-DD)")]


@training_router.post(
    "/import",
    response_model=ImportResult,
    responses=error_responses(400, 413),
)
def post_import(request: ImportPackageRequest):
    """Decode, validate, lint, and atomically activate one authored ZIP package."""
    return import_package(build_container().training_repo, request)


@training_router.get("/today", response_model=TrainingTodayResponse)
def get_today(date: _TodayDate):
    """Return one day's compiled training schedule merged with capture logs."""
    container = build_container()
    return get_training_today(
        container.training_repo,
        date=date.isoformat(),
        run_activity_port=container.training_run_activity_port,
        measurement_assessment_port=container.training_measurement_assessment_port,
    )


@training_router.get("/schedule-window", response_model=TrainingScheduleWindow)
def get_schedule_window(
    start: _ScheduleStartDate,
    days: int = Query(14, ge=1, le=60, description="Number of days in the window (1-60)"),
):
    """Return a multi-day training schedule projection starting at `start`."""
    container = build_container()
    return get_training_schedule_window(
        container.training_repo,
        start_date=start.isoformat(),
        duration_days=days,
        run_activity_port=container.training_run_activity_port,
        measurement_assessment_port=container.training_measurement_assessment_port,
    )


@training_router.get(
    "/block",
    response_model=TrainingBlockStatus,
    responses=error_responses(404),
)
def get_block():
    """Return the active block's lifecycle status, 404 when nothing is imported."""
    status = get_block_status(build_container().training_repo)
    if status is None:
        raise LookupError("No active training block")
    return status


@training_router.put(
    "/today/{date}/cards/{occurrence_key}",
    response_model=TrainingCardLog,
    responses=error_responses(400, 404),
)
def put_today_card_log(date: Date, occurrence_key: str, request: TrainingLogUpdateRequest):
    """Apply a partial update to one card occurrence's capture log."""
    container = build_container()
    return upsert_training_log(
        container.training_repo,
        date=date.isoformat(),
        occurrence_key=occurrence_key,
        update=request,
        run_activity_port=container.training_run_activity_port,
        measurement_assessment_port=container.training_measurement_assessment_port,
    )
