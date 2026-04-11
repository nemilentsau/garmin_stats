"""Compatibility wrapper for routines schedule projection."""

from app.bootstrap.container import build_container
from app.domains.routines.application.schedule_window import (
    get_schedule_window as _get_schedule_window,
)


def get_schedule_window(start_date: str, duration_days: int = 14):
    return _get_schedule_window(
        build_container().routines_repo, start_date=start_date, duration_days=duration_days
    )
