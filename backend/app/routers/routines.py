"""Compatibility wrapper for routines routes."""

from app.domains.routines.api.routines import router
from app.services.schedule_projection import get_schedule_window
from app.services.training_specs import get_routine, list_routine_assignments, list_routines

__all__ = [
    "router",
    "get_routine",
    "get_schedule_window",
    "list_routine_assignments",
    "list_routines",
]
