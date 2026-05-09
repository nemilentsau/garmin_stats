"""Shared helpers for daily scalar metric calculations."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.domains.garmin_health.contracts import DailyMetricStats
from app.utils.numeric import (
    summarize_scalar_values,
)


@dataclass(frozen=True, slots=True)
class DailyIntExtremaStats:
    """Daily distribution stats with integer-typed extrema."""

    avg: float | None
    min: int | None
    max: int | None
    median: float | None
    q1: float | None
    q3: float | None


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


def compute_daily_int_extrema_stats(
    values: Sequence[int],
) -> DailyIntExtremaStats:
    """Daily stats for int-valued metrics, preserving int extrema for the API."""
    summary = summarize_scalar_values(values)
    return DailyIntExtremaStats(
        avg=summary.avg,
        min=int(summary.min) if summary.min is not None else None,
        max=int(summary.max) if summary.max is not None else None,
        median=summary.median,
        q1=summary.q1,
        q3=summary.q3,
    )
