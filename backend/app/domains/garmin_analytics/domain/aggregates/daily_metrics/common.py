"""Shared helpers for daily scalar metric aggregates."""

from collections.abc import Sequence

from app.domains.garmin_analytics.contracts import DailyMetricStats
from app.domains.garmin_analytics.domain.primitives.numeric import (
    safe_avg,
    safe_max,
    safe_median,
    safe_min,
    safe_percentile,
)


def compute_daily_metric_stats(
    values: Sequence[int | float],
    *,
    rounded_extrema: bool = False,
) -> DailyMetricStats:
    """Compute common daily stats for scalar time-series metrics."""
    return DailyMetricStats(
        avg=safe_avg(values),
        min=safe_min(values) if rounded_extrema else min(values) if values else None,
        max=safe_max(values) if rounded_extrema else max(values) if values else None,
        median=safe_median(values),
        q1=safe_percentile(values, 25),
        q3=safe_percentile(values, 75),
    )
