"""Routine service."""

from ..infra.database import (
    load_routine_entries,
    load_routines,
    routine_exists,
    save_routine,
    save_routine_entry,
)
from ..models import Routine, RoutineEntriesResponse, RoutineEntry, RoutinesResponse


def _require_routine(routine_id: str) -> None:
    """Raise LookupError if the routine does not exist."""
    if not routine_exists(routine_id):
        raise LookupError(f"Routine {routine_id} not found")


def list_routines() -> RoutinesResponse:
    """Return all saved routines."""
    routines = load_routines()
    return RoutinesResponse(routines=routines, total=len(routines))


def create_routine(routine: Routine) -> Routine:
    """Create a new routine."""
    save_routine(routine)
    return routine


def update_routine(routine_id: str, routine: Routine) -> Routine:
    """Replace an existing routine."""
    if routine.id != routine_id:
        raise ValueError("Routine id does not match path id")
    _require_routine(routine_id)
    save_routine(routine)
    return routine


def list_routine_entries(routine_id: str, date: str | None = None) -> RoutineEntriesResponse:
    """Return entries for a specific routine."""
    _require_routine(routine_id)
    entries = load_routine_entries(routine_id=routine_id, date=date)
    return RoutineEntriesResponse(entries=entries, total=len(entries))


def create_routine_entry(routine_id: str, entry: RoutineEntry) -> RoutineEntry:
    """Create an entry for a routine."""
    if entry.routine_id != routine_id:
        raise ValueError("Routine entry routine_id does not match path id")
    _require_routine(routine_id)
    save_routine_entry(entry)
    return entry
