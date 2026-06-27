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
from app.domains.garmin_health.domain.daily_metrics.hrv import (
    classify_hrv_recovery as _classify_hrv_recovery,
)


def classify_hrv_recovery(*, delta: float | None, status: str | None) -> str | None:
    """Compatibility export for shared HRV recovery status classification."""
    return _classify_hrv_recovery(delta=delta, status=status)


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


def compute_pattern_window(
    metrics: list[DailyMetric],
    selected_nightly: float | None,
) -> HrvPatternWindow:
    """Distribution + day-of-week stats for a given slice of metrics."""
    nightly_vals = [
        m.hrv.nightly_avg for m in metrics if m.hrv.nightly_avg is not None
    ]
    return HrvPatternWindow(
        distribution=hrv_patterns.compute_hrv_distribution(
            nightly_vals, selected_nightly,
        ),
        day_of_week=hrv_patterns.compute_day_of_week(metrics),
    )


def compute_pattern_windows(
    metrics: list[DailyMetric],
    selected_nightly: float | None,
) -> dict[str, HrvPatternWindow]:
    """Pre-compute pattern stats for each time window."""
    return compute_windows(
        metrics,
        lambda subset: compute_pattern_window(subset, selected_nightly),
    )


def compute_hrv_analysis(
    metrics: list[DailyMetric],
    window: int = BASELINE_WINDOW_DEFAULT,
) -> HrvAnalysisResponse:
    """Compute HRV analysis read model from daily metrics."""
    selected_nightly: float | None = None
    if metrics and metrics[-1].hrv.nightly_avg is not None:
        selected_nightly = metrics[-1].hrv.nightly_avg
    return HrvAnalysisResponse(
        nightly_trend=compute_nightly_hrv_trend(metrics, window=window),
        pattern_windows=compute_pattern_windows(metrics, selected_nightly),
    )
