"""Compatibility wrapper for routines schedule projection."""

from functools import lru_cache

from app.domains.routines.application.schedule_window import (
    get_schedule_window as _get_schedule_window,
)
from app.domains.routines.domain.schedule import (
    SLOT_ORDER,
)
from app.domains.routines.domain.schedule import (
    override_occurrence_key as _override_occurrence_key,
)
from app.domains.routines.domain.schedule import (
    parse_schedule_date as _parse_schedule_date,
)
from app.domains.routines.domain.schedule import (
    scheduled_occurrence_key as _scheduled_occurrence_key,
)

_SLOT_ORDER = SLOT_ORDER
override_occurrence_key = _override_occurrence_key
parse_schedule_date = _parse_schedule_date
scheduled_occurrence_key = _scheduled_occurrence_key

__all__ = [
    "_SLOT_ORDER",
    "get_schedule_window",
    "override_occurrence_key",
    "parse_schedule_date",
    "scheduled_occurrence_key",
]


def get_schedule_window(start_date: str, duration_days: int = 14):
    return _get_schedule_window(_repo(), start_date=start_date, duration_days=duration_days)


@lru_cache(maxsize=1)
def _repo():
    from app.bootstrap.container import build_container

    return build_container().routines_repo
