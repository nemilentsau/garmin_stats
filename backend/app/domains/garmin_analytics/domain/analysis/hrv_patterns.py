"""Shared HRV pattern primitives for analysis and selected-day insights.

This module owns the reusable distribution and weekday helpers that feed both
the chart analysis read model and the HRV insights composer. It deliberately
stays below either caller, so analysis and insight modules can share the same
policy without importing each other.
"""

from datetime import date as date_type

from app.domains.garmin_analytics.contracts import (
    HrvDayOfWeekBucket,
    HrvDistribution,
    HrvDistributionBin,
)
from app.domains.garmin_health.contracts import (
    DailyMetric,
)
from app.utils.numeric import (
    histogram_bins,
    percentile_rank,
    safe_avg,
)

_HRV_DIST_MIN_DAYS = 7
_HRV_BIN_WIDTH = 5
_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def compute_hrv_distribution(
    nightly_vals: list[float],
    selected_value: float | None,
) -> HrvDistribution | None:
    """Build a 5 ms histogram of nightly HRV across the full period."""
    if len(nightly_vals) < _HRV_DIST_MIN_DAYS:
        return None

    bins = [
        HrvDistributionBin(
            bin_start=float(b.bin_start),
            bin_end=float(b.bin_end),
            count=b.count,
        )
        for b in histogram_bins(nightly_vals, _HRV_BIN_WIDTH)
    ]
    selected_percentile = (
        percentile_rank(nightly_vals, selected_value)
        if selected_value is not None else None
    )

    return HrvDistribution(
        bins=bins,
        total_days=len(nightly_vals),
        selected_value=selected_value,
        selected_percentile=selected_percentile,
    )


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
