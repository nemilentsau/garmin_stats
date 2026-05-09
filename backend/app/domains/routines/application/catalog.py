"""Catalog read use cases for compiled routines.

These functions expose live routine schedules and assignments through the
repository port, keeping HTTP and SQLite details outside the application layer.
"""

from __future__ import annotations

from app.domains.routines.contracts import (
    RoutineAssignmentsResponse,
    RoutineSchedule,
    RoutineSchedulesResponse,
)
from app.domains.routines.dependencies import RoutineRepository


def list_routines(
    repo: RoutineRepository,
    status: str | None = None,
) -> RoutineSchedulesResponse:
    """List compiled routine schedules, optionally filtered by status."""
    return RoutineSchedulesResponse(routines=repo.list_routines(status=status))


def get_routine(repo: RoutineRepository, routine_id: str) -> RoutineSchedule:
    """Load one compiled routine schedule or raise when it is missing."""
    routine = repo.get_routine(routine_id)
    if routine is None:
        raise LookupError(f"Routine {routine_id} not found")
    return routine


def list_routine_assignments(
    repo: RoutineRepository,
    routine_id: str,
) -> RoutineAssignmentsResponse:
    """List dated assignments for an existing compiled routine."""
    get_routine(repo, routine_id)
    return RoutineAssignmentsResponse(assignments=repo.list_assignments(routine_id=routine_id))
