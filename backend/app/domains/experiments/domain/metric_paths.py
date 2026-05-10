"""Experiment metric path resolution helpers."""

from __future__ import annotations

from pydantic import BaseModel

from app.domains.garmin_health.contracts import DailyMetric
from app.domains.journal.contracts import DailyCheckIn


def resolve_metric_path(metric: DailyMetric, path: str) -> float | None:
    """Resolve a dotted path like 'hrv.nightly_avg' to a numeric value."""
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
    """Resolve a checkin field. *path* should NOT include the 'checkin.' prefix."""
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
    """Dispatch to the right resolver based on path prefix."""
    if path.startswith("checkin."):
        if checkin is None:
            return None
        return resolve_checkin_path(checkin, path.removeprefix("checkin."))
    if metric is None:
        return None
    return resolve_metric_path(metric, path)
