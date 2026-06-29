"""HRV weekday pattern primitives for the analysis read model.

This module owns the weekday helper that feeds the chart analysis read model
(``compute_pattern_window`` / ``compute_day_of_week``). Selected-day insights dropped
day-of-week, so the analysis layer is now its only consumer; the helper stays in this
standalone module so the per-window pattern policy lives in one focused place rather than
inline in the larger analysis composer.
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
