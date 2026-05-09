"""Shared helpers for period scalar metric summaries."""

from collections.abc import Sequence

from app.domains.garmin_analytics.contracts import PeriodMetricStats
from app.utils.numeric import (
    safe_avg,
    safe_percentile,
)


def compute_period_metric_stats(values: Sequence[int | float]) -> PeriodMetricStats:
    """Compute shared period stats for raw scalar readings."""
    return PeriodMetricStats(
        avg=safe_avg(values),
        typical_low=safe_percentile(values, 25),
        typical_high=safe_percentile(values, 75),
    )
