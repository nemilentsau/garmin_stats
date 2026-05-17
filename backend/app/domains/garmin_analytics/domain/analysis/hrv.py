"""HRV analysis calculations for Garmin analytics."""

from app.domains.garmin_analytics.contracts import (
    HrvAnalysisResponse,
    HrvPatternWindow,
    NightlyHrvTrendPoint,
    WeeklyHrvBox,
)
from app.domains.garmin_analytics.domain.analysis import hrv_patterns
from app.domains.garmin_analytics.domain.primitives.trends import (
    trailing_ma7,
    weekly_five_number_summaries,
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
) -> list[NightlyHrvTrendPoint]:
    """Raw nightly HRV + 7-day trailing moving average."""
    nightly_values: list[float | None] = [m.hrv.nightly_avg for m in metrics]
    ma7_values = trailing_ma7(nightly_values)

    return [
        NightlyHrvTrendPoint(
            date=m.date,
            nightly_avg=nightly_values[i],
            ma7=ma7_values[i],
        )
        for i, m in enumerate(metrics)
    ]


def compute_weekly_hrv_boxplots(
    metrics: list[DailyMetric],
) -> list[WeeklyHrvBox]:
    """Group nightly HRV by ISO week, compute 5-number summary."""
    summaries = weekly_five_number_summaries(metrics, lambda m: m.hrv.nightly_avg)
    return [
        WeeklyHrvBox(
            iso_week=summary.iso_week,
            min_ms=summary.min,
            q1_ms=summary.q1,
            median_ms=summary.median,
            q3_ms=summary.q3,
            max_ms=summary.max,
            day_count=summary.count,
        )
        for summary in summaries
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


def compute_hrv_analysis(metrics: list[DailyMetric]) -> HrvAnalysisResponse:
    """Compute HRV analysis read model from daily metrics."""
    selected_nightly: float | None = None
    if metrics and metrics[-1].hrv.nightly_avg is not None:
        selected_nightly = metrics[-1].hrv.nightly_avg
    return HrvAnalysisResponse(
        nightly_trend=compute_nightly_hrv_trend(metrics),
        weekly_boxplots=compute_weekly_hrv_boxplots(metrics),
        pattern_windows=compute_pattern_windows(metrics, selected_nightly),
    )
