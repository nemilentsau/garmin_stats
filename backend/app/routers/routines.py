"""Routine schedule HTTP routes."""

from fastapi import APIRouter, HTTPException, Query

from ..models import (
    RoutineAssignmentsResponse,
    RoutineSchedule,
    RoutineSchedulesResponse,
    ScheduleWindow,
)
from ..services.schedule_projection import get_schedule_window
from ..services.training_specs import get_routine, list_routine_assignments, list_routines

router = APIRouter(prefix="/api/routines", tags=["routines"])


@router.get("", response_model=RoutineSchedulesResponse)
def get_routines(status: str | None = None):
    """Return compiled live routines."""
    return list_routines(status=status)


@router.get("/schedule-window", response_model=ScheduleWindow)
def get_routine_schedule_window(
    start_date: str = Query(..., description="Start date for the 14-day schedule window"),
):
    """Return resolved dated occurrences for the next 14 days."""
    try:
        return get_schedule_window(start_date)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.get("/{routine_id}", response_model=RoutineSchedule)
def get_routine_detail(routine_id: str):
    """Return a single compiled live routine."""
    try:
        return get_routine(routine_id)
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.get("/{routine_id}/assignments", response_model=RoutineAssignmentsResponse)
def get_assignments(routine_id: str):
    """Return recurring card assignments for a routine."""
    try:
        return list_routine_assignments(routine_id)
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
