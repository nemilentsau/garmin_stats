"""Routine schedule HTTP routes."""

from fastapi import APIRouter, HTTPException

from ..models import RoutineAssignmentsResponse, RoutineSchedule, RoutineSchedulesResponse
from ..services.training_specs import get_routine, list_routine_assignments, list_routines

router = APIRouter(prefix="/api/routines", tags=["routines"])


@router.get("", response_model=RoutineSchedulesResponse)
def get_routines(status: str | None = None):
    """Return compiled live routines."""
    return list_routines(status=status)


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
