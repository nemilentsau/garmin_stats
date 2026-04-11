"""Catalog use cases for routines."""

from __future__ import annotations

from app.models import RoutineAssignmentsResponse, RoutineSchedule, RoutineSchedulesResponse

from .ports import RoutineRepository


def list_routines(
    repo: RoutineRepository,
    status: str | None = None,
) -> RoutineSchedulesResponse:
    return RoutineSchedulesResponse(routines=repo.list_routines(status=status))


def get_routine(repo: RoutineRepository, routine_id: str) -> RoutineSchedule:
    routine = repo.get_routine(routine_id)
    if routine is None:
        raise LookupError(f"Routine {routine_id} not found")
    return routine


def list_routine_assignments(
    repo: RoutineRepository,
    routine_id: str,
) -> RoutineAssignmentsResponse:
    get_routine(repo, routine_id)
    return RoutineAssignmentsResponse(assignments=repo.list_assignments(routine_id=routine_id))
