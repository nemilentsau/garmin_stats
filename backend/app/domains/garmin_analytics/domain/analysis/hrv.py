"""HRV analysis calculations for Garmin analytics."""

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
from app.utils.timeutil import date_range

# A weekday average this many ms off the window's grand mean colours its bar (caution/elevated);
# inside the band it reads neutral. Owned here, not in the frontend, so the bar-colour policy is
# backend-authoritative (the frontend maps the state to a colour and computes nothing).
DAY_OF_WEEK_DELTA_MS = 5.0


def _day_of_week_state(
    avg_nightly: float | None, overall_avg: float | None
) -> str | None:
    """Classify a weekday's average against the window grand mean (below / within / above).

    None when either input is missing (no nights for the weekday, or no grand mean), so the bar
    renders neutral. Mirrors the strip's ``trend_state`` vocabulary; see ``DAY_OF_WEEK_DELTA_MS``.
    """
    if avg_nightly is None or overall_avg is None:
        return None
    diff = avg_nightly - overall_avg
    if diff > DAY_OF_WEEK_DELTA_MS:
        return "above"
    if diff < -DAY_OF_WEEK_DELTA_MS:
        return "below"
    return "within"


def _trend_state(
    ma7: float | None, band_low: float | None, band_high: float | None
) -> str | None:
    """Where the 7-day MA sits relative to the trailing typical-range band.

    The historical strip colors by this (the averaged trend), not by a single night's
    status — a single night is noise. None during warmup/gaps (no band or no MA).
    """
    if ma7 is None or band_low is None or band_high is None:
        return None
    # A degenerate trailing window (zero spread) collapses the band to a point
    # (band_low == band_high, per trailing_band_point). With no spread there is nothing to be
    # "below" or "above", so the trend is "within" — never a garbage extreme from ma7 differing
    # in the sub-rounding digits.
    if band_low >= band_high:
        return "within"
    if ma7 < band_low:
        return "below"
    if ma7 > band_high:
        return "above"
    return "within"


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
    # The trailing MA/band primitives below read each night's *prior* N nights positionally, so
    # they require chronological order — as does the date_range() densification at the end, which
    # would return [] for a newest-first input. Sort defensively so the trend is correct (and
    # never silently empty) regardless of how a caller ordered the metrics.
    metrics = sorted(metrics, key=lambda m: m.date)
    nightly_values: list[float | None] = [m.hrv.nightly_avg for m in metrics]
    ma7_values = trailing_ma7(nightly_values)
    band = trailing_robust_band(nightly_values, window=window, min_days=BASELINE_MIN_DAYS)

    points_by_date: dict[str, NightlyHrvTrendPoint] = {}
    for i, m in enumerate(metrics):
        # The strip's trend color is the same whether or not the night has a reading, so
        # compute it once — the gap and present branches must never classify it differently.
        trend_state = _trend_state(ma7_values[i], band[i].band_low, band[i].band_high)
        if nightly_values[i] is None:
            # Night with no HRV reading: the chart fields stay null so the MA line and ribbon
            # break here (a missing night is never bridged). The history strip, however, is a
            # trend heatmap — it still colors by the surrounding 7-day trend so a single
            # missing night doesn't punch a gray hole in it. So carry trend_state (computed
            # from the trailing MA/band, which are defined past warmup) on the otherwise-null
            # gap point.
            points_by_date[m.date] = NightlyHrvTrendPoint(date=m.date, trend_state=trend_state)
        else:
            points_by_date[m.date] = NightlyHrvTrendPoint(
                date=m.date,
                nightly_avg=nightly_values[i],
                ma7=ma7_values[i],
                band_low=band[i].band_low,
                band_high=band[i].band_high,
                z=band[i].z,
                is_extreme=band[i].is_extreme,
                trend_state=trend_state,
            )

    # Fill entirely-absent calendar days (no row) with gap points too, so device-off
    # stretches break the line rather than being bridged by the time axis.
    return [
        points_by_date.get(d, NightlyHrvTrendPoint(date=d))
        for d in date_range(metrics[0].date, metrics[-1].date)
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
    overall_avg = safe_avg(nightly_vals)
    # Classify each weekday vs the grand mean on the backend so the frontend colours bars from a
    # backend-authoritative `state` and does no statistics of its own (matches the strip's
    # trend_state; see docs/reference/hrv.md "Trend versus one night").
    for bucket in day_of_week:
        bucket.state = _day_of_week_state(bucket.avg_nightly, overall_avg)
    return HrvPatternWindow(
        day_of_week=day_of_week,
        overall_avg=overall_avg,
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
