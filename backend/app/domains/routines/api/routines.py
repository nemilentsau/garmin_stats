"""Domain-local routines routes."""

from fastapi import APIRouter, Query

from app.bootstrap.container import build_container
from app.domains.routines.application.catalog import (
    get_routine,
    list_routine_assignments,
    list_routines,
)
from app.domains.routines.application.schedule_window import get_schedule_window
from app.models import (
    RoutineAssignmentsResponse,
    RoutineSchedule,
    RoutineSchedulesResponse,
    ScheduleWindow,
)

router = APIRouter(prefix="/api/routines", tags=["routines"])


@router.get("", response_model=RoutineSchedulesResponse)
def get_routines(status: str | None = None):
    """Return compiled live routines."""
    return list_routines(build_container().routines_repo, status=status)


@router.get("/schedule-window", response_model=ScheduleWindow)
def get_routine_schedule_window(
    start_date: str = Query(..., description="Start date for the 14-day schedule window"),
):
    """Return resolved dated occurrences for the next 14 days."""
    return get_schedule_window(build_container().routines_repo, start_date=start_date)


@router.get("/{routine_id}", response_model=RoutineSchedule)
def get_routine_detail(routine_id: str):
    """Return a single compiled live routine."""
    return get_routine(build_container().routines_repo, routine_id)


@router.get("/{routine_id}/assignments", response_model=RoutineAssignmentsResponse)
def get_assignments(routine_id: str):
    """Return recurring card assignments for a routine."""
    return list_routine_assignments(build_container().routines_repo, routine_id=routine_id)
