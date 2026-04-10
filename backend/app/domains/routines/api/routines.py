"""Domain-local routines routes."""

from fastapi import APIRouter, Query

from app.models import (
    RoutineAssignmentsResponse,
    RoutineSchedule,
    RoutineSchedulesResponse,
    ScheduleWindow,
)

router = APIRouter(prefix="/api/routines", tags=["routines"])


@router.get("", response_model=RoutineSchedulesResponse)
def get_routines(status: str | None = None):
    from app.routers import routines as compat_routines

    return compat_routines.list_routines(status=status)


@router.get("/schedule-window", response_model=ScheduleWindow)
def get_routine_schedule_window(
    start_date: str = Query(..., description="Start date for the 14-day schedule window"),
):
    from app.routers import routines as compat_routines

    return compat_routines.get_schedule_window(start_date)


@router.get("/{routine_id}", response_model=RoutineSchedule)
def get_routine_detail(routine_id: str):
    from app.routers import routines as compat_routines

    return compat_routines.get_routine(routine_id)


@router.get("/{routine_id}/assignments", response_model=RoutineAssignmentsResponse)
def get_assignments(routine_id: str):
    from app.routers import routines as compat_routines

    return compat_routines.list_routine_assignments(routine_id)
