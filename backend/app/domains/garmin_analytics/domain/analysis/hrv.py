"""HRV analysis calculations for Garmin analytics."""

from datetime import date as date_type
from datetime import timedelta

from app.domains.garmin_analytics.contracts import (
    HrvPatternWindow,
    NightlyHrvTrendPoint,
)
from app.domains.garmin_analytics.domain.analysis import hrv_patterns
from app.domains.garmin_analytics.domain.primitives.trends import (
    BASELINE_MIN_DAYS,
    BASELINE_WINDOW_DEFAULT,
    trailing_ma7,
    trailing_robust_band,
)
from app.domains.garmin_analytics.domain.primitives.windows import compute_windows
from app.domains.garmin_health.contracts import (
    DailyMetric,
)
from app.utils.numeric import safe_avg


def _daily_calendar(start_iso: str, end_iso: str) -> list[str]:
    """Inclusive list of ISO dates from ``start_iso`` to ``end_iso``, one per calendar day."""
    start = date_type.fromisoformat(start_iso)
    end = date_type.fromisoformat(end_iso)
    return [(start + timedelta(days=n)).isoformat() for n in range((end - start).days + 1)]


def compute_nightly_hrv_trend(
    metrics: list[DailyMetric],
    window: int = BASELINE_WINDOW_DEFAULT,
) -> list[NightlyHrvTrendPoint]:
    """Nightly HRV with its 7-day MA and a trailing robust baseline band.

    The series is densified to a complete daily calendar so that nights with no HRV reading
    — whether the day is entirely absent (no row) or present with a null reading — appear as
    explicit all-null gap points. Combined with ``spanGaps: false`` on the frontend, the MA
    line and the ribbon break across gaps instead of bridging a straight segment over data
    that was never observed (a missing night is a between-process gap; it is skipped, never
    interpolated). The band/MA are computed over the present-reading series exactly as the
    selected-day panel computes them, so the chart and the panel still agree for any night
    and window.
    """
    if not metrics:
        return []
    nightly_values: list[float | None] = [m.hrv.nightly_avg for m in metrics]
    ma7_values = trailing_ma7(nightly_values)
    band = trailing_robust_band(nightly_values, window=window, min_days=BASELINE_MIN_DAYS)

    points_by_date: dict[str, NightlyHrvTrendPoint] = {}
    for i, m in enumerate(metrics):
        if nightly_values[i] is None:
            # Night with no HRV reading: an all-null gap point so every series breaks here.
            points_by_date[m.date] = NightlyHrvTrendPoint(date=m.date)
        else:
            points_by_date[m.date] = NightlyHrvTrendPoint(
                date=m.date,
                nightly_avg=nightly_values[i],
                ma7=ma7_values[i],
                band_low=band[i].band_low,
                band_high=band[i].band_high,
                z=band[i].z,
                is_extreme=band[i].is_extreme,
            )

    # Fill entirely-absent calendar days (no row) with gap points too, so device-off
    # stretches break the line rather than being bridged by the time axis.
    return [
        points_by_date.get(d, NightlyHrvTrendPoint(date=d))
        for d in _daily_calendar(metrics[0].date, metrics[-1].date)
    ]


def compute_pattern_window(metrics: list[DailyMetric]) -> HrvPatternWindow:
    """Day-of-week stats for a given slice of metrics.

    ``overall_avg`` is the sample-weighted grand mean (not a mean-of-means) so
    the frontend can colour day-of-week bars relative to a backend-authoritative
    reference without any in-browser computation. ``total_sample_count`` carries the
    night count for the same reason — the frontend renders it directly instead of
    summing the buckets itself.
    """
    nightly_vals = [
        m.hrv.nightly_avg for m in metrics if m.hrv.nightly_avg is not None
    ]
    day_of_week = hrv_patterns.compute_day_of_week(metrics)
    return HrvPatternWindow(
        day_of_week=day_of_week,
        overall_avg=safe_avg(nightly_vals),
        # Sum the buckets (not len(nightly_vals)) so the total always equals what the
        # chart actually plots, and the frontend never has to aggregate.
        total_sample_count=sum(b.sample_count for b in day_of_week),
    )


def compute_pattern_windows(metrics: list[DailyMetric]) -> dict[str, HrvPatternWindow]:
    """Pre-compute pattern stats for each time window.

    Baseline-independent: callers (the analysis loader) cache the result once and reuse it
    across baseline windows, assembling the ``HrvAnalysisResponse`` alongside the per-window
    nightly trend from ``compute_nightly_hrv_trend``.
    """
    return compute_windows(
        metrics,
        compute_pattern_window,
    )
