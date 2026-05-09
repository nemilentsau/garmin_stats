"""HTTP routes for the routines domain."""

from fastapi import APIRouter, Query

from app.bootstrap.container import build_container
from app.domains.routines.application.catalog import (
    get_routine,
    list_routine_assignments,
    list_routines,
)
from app.domains.routines.application.schedule_window import get_schedule_window
from app.domains.routines.application.today import (
    get_card_log_range as _get_card_log_range,
)
from app.domains.routines.application.today import (
    get_today as _get_today,
)
from app.domains.routines.application.today import (
    upsert_today_card_log as _upsert_today_card_log,
)
from app.domains.routines.contracts import (
    CardLog,
    CardLogRangeResponse,
    RoutineAssignmentsResponse,
    RoutineSchedule,
    RoutineSchedulesResponse,
    ScheduleWindow,
    TodayCardLogUpdateRequest,
    TodayResponse,
)

routines_router = APIRouter(prefix="/api/routines", tags=["routines"])
today_router = APIRouter(prefix="/api/today", tags=["today"])


@routines_router.get("", response_model=RoutineSchedulesResponse)
def get_routines(status: str | None = None):
    """Return compiled live routines."""
    return list_routines(build_container().routines_repo, status=status)


@routines_router.get("/schedule-window", response_model=ScheduleWindow)
def get_routine_schedule_window(
    start_date: str = Query(..., description="Start date for the 14-day schedule window"),
):
    """Return resolved dated occurrences for the next 14 days."""
    return get_schedule_window(build_container().routines_repo, start_date=start_date)


@routines_router.get("/{routine_id}", response_model=RoutineSchedule)
def get_routine_detail(routine_id: str):
    """Return a single compiled live routine."""
    return get_routine(build_container().routines_repo, routine_id)


@routines_router.get("/{routine_id}/assignments", response_model=RoutineAssignmentsResponse)
def get_assignments(routine_id: str):
    """Return recurring card assignments for a routine."""
    return list_routine_assignments(build_container().routines_repo, routine_id=routine_id)


@today_router.get("", response_model=TodayResponse)
def get_today_view(date: str = Query(..., description="Date (YYYY-MM-DD)")):
    """Return compiled cards for a single day."""
    return _get_today(build_container().routines_repo, date=date)


@today_router.get("/card-logs", response_model=CardLogRangeResponse)
def get_card_logs_range(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD, inclusive)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD, inclusive)"),
):
    """Return completion statuses for all card occurrences in a date range."""
    repo = build_container().routines_repo
    return _get_card_log_range(repo, start_date=start_date, end_date=end_date)


@today_router.put("/{date}/cards/{occurrence_key}", response_model=CardLog)
def put_today_card_log(date: str, occurrence_key: str, request: TodayCardLogUpdateRequest):
    """Create or replace the log for a single card occurrence."""
    container = build_container()
    return _upsert_today_card_log(
        container.routines_repo,
        date=date,
        occurrence_key=occurrence_key,
        request=request,
        observer=container.experiment_exposure_sync,
    )
