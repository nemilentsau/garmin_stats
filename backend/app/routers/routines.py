"""Compatibility wrapper for routines routes."""

from app.domains.routines.api.routines import router
from app.services.schedule_projection import get_schedule_window

__all__ = [
    "router",
    "get_schedule_window",
]
