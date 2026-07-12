"""HTTP routes for v3 training import, Today/schedule views, and capture logs.

Routes bind FastAPI request/response metadata to the training application use
cases (`application/imports.py`, `application/read_models.py`). They resolve
the repository from the app container and leave artifact validation,
schedule compilation, display projection, and capture-log persistence to
those modules — this file has no policy of its own beyond the LookupError ->
404 fallback for "no active block", handled by the app-level exception
handler registered in `bootstrap/app.py`.
"""

from fastapi import APIRouter, Query

from app.bootstrap.container import build_container
from app.domains.training.application.imports import ImportRequest, ImportResult, import_artifacts
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


@training_router.post("/import", response_model=ImportResult)
def post_import(request: ImportRequest):
    """Validate, lint, and single-shot activate an uploaded v3 artifact set."""
    return import_artifacts(build_container().training_repo, request)


@training_router.get("/today", response_model=TrainingTodayResponse)
def get_today(date: str = Query(..., description="Date (YYYY-MM-DD)")):
    """Return one day's compiled training schedule merged with capture logs."""
    container = build_container()
    return get_training_today(
        container.training_repo, date=date, run_activity_port=container.training_run_activity_port
    )


@training_router.get("/schedule-window", response_model=TrainingScheduleWindow)
def get_schedule_window(
    start: str = Query(..., description="Start date (YYYY-MM-DD)"),
    days: int = Query(14, description="Number of days in the window"),
):
    """Return a multi-day training schedule projection starting at `start`."""
    return get_training_schedule_window(
        build_container().training_repo, start_date=start, duration_days=days
    )


@training_router.get("/block", response_model=TrainingBlockStatus)
def get_block():
    """Return the active block's lifecycle status, 404 when nothing is imported."""
    status = get_block_status(build_container().training_repo)
    if status is None:
        raise LookupError("No active training block")
    return status


@training_router.put("/today/{date}/cards/{occurrence_key}", response_model=TrainingCardLog)
def put_today_card_log(date: str, occurrence_key: str, request: TrainingLogUpdateRequest):
    """Apply a partial update to one card occurrence's capture log."""
    container = build_container()
    return upsert_training_log(
        container.training_repo,
        date=date,
        occurrence_key=occurrence_key,
        update=request,
        run_activity_port=container.training_run_activity_port,
    )
