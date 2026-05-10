"""Experiment metric path resolution helpers.

Experiment specs store dotted paths instead of binding directly to Garmin or
check-in model fields. These helpers resolve those paths safely and return only
scalar values that the analysis pipeline can compare.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.domains.garmin_health.contracts import DailyMetric
from app.domains.journal.contracts import DailyCheckIn


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
    if path.startswith("checkin."):
        if checkin is None:
            return None
        return resolve_checkin_path(checkin, path.removeprefix("checkin."))
    if metric is None:
        return None
    return resolve_metric_path(metric, path)
