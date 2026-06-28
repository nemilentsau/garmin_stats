"""Shared HRV weekday pattern primitives for analysis and selected-day insights.

This module owns the reusable weekday helper that feeds the chart analysis read
model and selected-day context. It deliberately stays below either caller, so
analysis and insight modules can share the same policy without importing each
other.
"""

from datetime import date as date_type

from app.domains.garmin_analytics.contracts import (
    HrvDayOfWeekBucket,
)
from app.domains.garmin_health.contracts import (
    DailyMetric,
)
from app.utils.numeric import (
    safe_avg,
)

_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def compute_day_of_week(metrics: list[DailyMetric]) -> list[HrvDayOfWeekBucket]:
    """Average nightly HRV grouped by weekday across the full dataset."""
    groups: dict[int, list[float]] = {i: [] for i in range(7)}
    for m in metrics:
        if m.hrv.nightly_avg is not None:
            try:
                weekday = date_type.fromisoformat(m.date).weekday()
            except ValueError:
                continue
            groups[weekday].append(m.hrv.nightly_avg)

    return [
        HrvDayOfWeekBucket(
            day=_DAY_NAMES[i],
            day_index=i,
            avg_nightly=safe_avg(vals),
            sample_count=len(vals),
        )
        for i, vals in sorted(groups.items())
    ]
