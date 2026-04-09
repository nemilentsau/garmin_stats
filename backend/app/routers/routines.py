"""Compatibility wrapper for routines routes."""

from app.domains.routines.api.routines import router
from app.services.schedule_projection import get_schedule_window
from app.services.training_specs import get_routine, list_routine_assignments, list_routines


def get_routines(status: str | None = None):
    return list_routines(status=status)


def get_routine_schedule_window(start_date: str):
    return get_schedule_window(start_date)


def get_routine_detail(routine_id: str):
    return get_routine(routine_id)


def get_assignments(routine_id: str):
    return list_routine_assignments(routine_id)

__all__ = [
    "router",
    "get_schedule_window",
    "get_routine",
    "list_routine_assignments",
    "list_routines",
    "get_routines",
    "get_routine_schedule_window",
    "get_routine_detail",
    "get_assignments",
]
