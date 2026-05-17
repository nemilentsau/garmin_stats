"""Experiment metric path resolution helpers.

Experiment specs store dotted paths instead of binding directly to Garmin or
check-in model fields. These helpers resolve those paths safely and return only
scalar values that the analysis pipeline can compare.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.domains.garmin_health.contracts import DailyMetric
from app.domains.journal.contracts import DailyCheckIn

CHECKIN_PATH_PREFIX = "checkin."
_CHECKIN_NON_SCALAR_FIELDS = frozenset({"id", "date", "notes"})
_VALID_CHECKIN_FIELDS = frozenset(
    field
    for field in DailyCheckIn.model_fields
    if field not in _CHECKIN_NON_SCALAR_FIELDS
)


def resolve_metric_path(metric: DailyMetric, path: str) -> float | None:
    """Resolve a dotted Garmin metric path to a numeric value."""
    current: object = metric
    for part in path.split("."):
        if current is None:
            return None
        if isinstance(current, BaseModel):
            current = getattr(current, part, None)
        else:
            return None
    if isinstance(current, (int, float)) and not isinstance(current, bool):
        return float(current)
    return None


def is_valid_checkin_path(path: str) -> bool:
    """Return whether a dotted check-in path names a supported scalar field."""
    if not path.startswith(CHECKIN_PATH_PREFIX):
        return False
    return path.removeprefix(CHECKIN_PATH_PREFIX) in _VALID_CHECKIN_FIELDS


def resolve_checkin_path(checkin: DailyCheckIn, path: str) -> float | bool | None:
    """Resolve a check-in field path without the ``checkin.`` prefix."""
    val = getattr(checkin, path, None)
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return float(val)
    return None


def resolve_path(
    metric: DailyMetric | None,
    checkin: DailyCheckIn | None,
    path: str,
) -> float | bool | None:
    """Resolve a metric or check-in path based on its prefix."""
    if path.startswith(CHECKIN_PATH_PREFIX):
        if checkin is None:
            return None
        return resolve_checkin_path(checkin, path.removeprefix(CHECKIN_PATH_PREFIX))
    if metric is None:
        return None
    return resolve_metric_path(metric, path)
