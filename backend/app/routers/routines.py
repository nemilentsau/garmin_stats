"""Routine HTTP routes."""

from fastapi import APIRouter, HTTPException, Query

from ..models import Routine, RoutineEntriesResponse, RoutineEntry, RoutinesResponse
from ..services.routines import (
    create_routine,
    create_routine_entry,
    list_routine_entries,
    list_routine_entries_by_date,
    list_routines,
    update_routine,
)

router = APIRouter(prefix="/api/routines", tags=["routines"])


@router.get("", response_model=RoutinesResponse)
def get_routines():
    """Return all routines."""
    return list_routines()


@router.post("", response_model=Routine)
def post_routine(routine: Routine):
    """Create a routine."""
    return create_routine(routine)


@router.put("/{routine_id}", response_model=Routine)
def put_routine(routine_id: str, routine: Routine):
    """Replace an existing routine."""
    try:
        return update_routine(routine_id, routine)
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.get("/entries", response_model=RoutineEntriesResponse)
def get_entries_by_date(
    date: str = Query(..., description="Date (YYYY-MM-DD)"),
):
    """Return all routine entries for a given date across all routines."""
    return list_routine_entries_by_date(date)


@router.get("/{routine_id}/entries", response_model=RoutineEntriesResponse)
def get_entries(
    routine_id: str,
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Return entries for a routine."""
    try:
        return list_routine_entries(routine_id, date=date)
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.post("/{routine_id}/entries", response_model=RoutineEntry)
def post_entry(routine_id: str, entry: RoutineEntry):
    """Create an entry for a routine."""
    try:
        return create_routine_entry(routine_id, entry)
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
