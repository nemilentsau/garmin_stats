"""Shared helpers for raw-period scalar metric aggregates."""

from collections.abc import Sequence

from app.domains.garmin_analytics.contracts import PeriodMetricStats
from app.domains.garmin_analytics.domain.primitives.numeric import (
    safe_avg,
    safe_percentile,
)


def compute_period_metric_stats(values: Sequence[int | float]) -> PeriodMetricStats:
    return PeriodMetricStats(
        avg=safe_avg(values),
        typical_low=safe_percentile(values, 25),
        typical_high=safe_percentile(values, 75),
    )
