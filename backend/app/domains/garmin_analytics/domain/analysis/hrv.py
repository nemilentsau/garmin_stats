"""HRV analysis calculations for Garmin analytics."""

from app.domains.garmin_analytics.contracts import (
    HrvAnalysisResponse,
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


def compute_nightly_hrv_trend(
    metrics: list[DailyMetric],
    window: int = BASELINE_WINDOW_DEFAULT,
) -> list[NightlyHrvTrendPoint]:
    """Nightly HRV with its 7-day MA and a trailing robust baseline band."""
    nightly_values: list[float | None] = [m.hrv.nightly_avg for m in metrics]
    ma7_values = trailing_ma7(nightly_values)
    band = trailing_robust_band(nightly_values, window=window, min_days=BASELINE_MIN_DAYS)

    return [
        NightlyHrvTrendPoint(
            date=m.date,
            nightly_avg=nightly_values[i],
            ma7=ma7_values[i],
            band_low=band[i].band_low,
            band_high=band[i].band_high,
            z=band[i].z,
            is_extreme=band[i].is_extreme,
        )
        for i, m in enumerate(metrics)
    ]


def compute_pattern_window(metrics: list[DailyMetric]) -> HrvPatternWindow:
    """Day-of-week stats for a given slice of metrics.

    ``overall_avg`` is the sample-weighted grand mean (not a mean-of-means) so
    the frontend can colour day-of-week bars relative to a backend-authoritative
    reference without any in-browser computation.
    """
    nightly_vals = [
        m.hrv.nightly_avg for m in metrics if m.hrv.nightly_avg is not None
    ]
    return HrvPatternWindow(
        day_of_week=hrv_patterns.compute_day_of_week(metrics),
        overall_avg=safe_avg(nightly_vals),
    )


def compute_pattern_windows(metrics: list[DailyMetric]) -> dict[str, HrvPatternWindow]:
    """Pre-compute pattern stats for each time window."""
    return compute_windows(
        metrics,
        compute_pattern_window,
    )


def compute_hrv_analysis(
    metrics: list[DailyMetric],
    window: int = BASELINE_WINDOW_DEFAULT,
) -> HrvAnalysisResponse:
    """Compute HRV analysis read model from daily metrics."""
    return HrvAnalysisResponse(
        nightly_trend=compute_nightly_hrv_trend(metrics, window=window),
        pattern_windows=compute_pattern_windows(metrics),
    )
