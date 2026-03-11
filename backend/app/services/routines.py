"""Routine service."""

from ..infra.database import (
    load_routine_entries,
    load_routines,
    save_routine,
    save_routine_entry,
)
from ..models import Routine, RoutineEntriesResponse, RoutineEntry, RoutinesResponse


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
    if not any(item.id == routine_id for item in load_routines()):
        raise LookupError(f"Routine {routine_id} not found")
    save_routine(routine)
    return routine


def list_routine_entries(routine_id: str, date: str | None = None) -> RoutineEntriesResponse:
    """Return entries for a specific routine."""
    if not any(item.id == routine_id for item in load_routines()):
        raise LookupError(f"Routine {routine_id} not found")
    entries = load_routine_entries(routine_id=routine_id, date=date)
    return RoutineEntriesResponse(entries=entries, total=len(entries))


def create_routine_entry(routine_id: str, entry: RoutineEntry) -> RoutineEntry:
    """Create an entry for a routine."""
    if entry.routine_id != routine_id:
        raise ValueError("Routine entry routine_id does not match path id")
    if not any(item.id == routine_id for item in load_routines()):
        raise LookupError(f"Routine {routine_id} not found")
    save_routine_entry(entry)
    return entry
