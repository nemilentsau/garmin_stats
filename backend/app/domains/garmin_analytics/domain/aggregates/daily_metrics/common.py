"""Shared helpers for daily scalar metric aggregates."""

from collections.abc import Sequence

from app.domains.garmin_analytics.contracts import DailyMetricStats
from app.domains.garmin_analytics.domain.primitives.numeric import (
    summarize_scalar_values,
)


def compute_daily_metric_stats(
    values: Sequence[int | float],
    *,
    rounded_extrema: bool = False,
) -> DailyMetricStats:
    """Compute common daily stats for scalar time-series metrics."""
    summary = summarize_scalar_values(values, rounded_extrema=rounded_extrema)
    return DailyMetricStats(
        avg=summary.avg,
        min=summary.min,
        max=summary.max,
        median=summary.median,
        q1=summary.q1,
        q3=summary.q3,
    )
