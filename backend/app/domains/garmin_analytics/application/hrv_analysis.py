"""HRV analysis calculations for Garmin analytics."""

from app.domains.garmin_analytics.application.hrv import (
    _compute_day_of_week,
    _compute_hrv_distribution,
)
from app.domains.garmin_analytics.application.ports import BiometricReadRepository
from app.domains.garmin_analytics.domain.windows import compute_windows
from app.infra import cache
from app.models import (
    DailyMetric,
    HrvAnalysisResponse,
    HrvPatternWindow,
    NightlyHrvTrendPoint,
    WeeklyHrvBox,
)
from app.stats import group_by_iso_week, safe_percentile, trailing_ma7


def _compute_nightly_hrv_trend(
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


def _compute_weekly_hrv_boxplots(
    metrics: list[DailyMetric],
) -> list[WeeklyHrvBox]:
    """Group nightly HRV by ISO week, compute 5-number summary."""
    weeks = group_by_iso_week(metrics, lambda m: m.hrv.nightly_avg)
    result: list[WeeklyHrvBox] = []
    for week_key in sorted(weeks):
        vals = sorted(weeks[week_key])
        result.append(
            WeeklyHrvBox(
                iso_week=week_key,
                min_ms=float(vals[0]),
                q1_ms=safe_percentile(vals, 25),
                median_ms=safe_percentile(vals, 50),
                q3_ms=safe_percentile(vals, 75),
                max_ms=float(vals[-1]),
                day_count=len(vals),
            )
        )
    return result


def _compute_pattern_window(
    metrics: list[DailyMetric],
    selected_nightly: float | None,
) -> HrvPatternWindow:
    """Distribution + day-of-week stats for a given slice of metrics."""
    nightly_vals = [
        m.hrv.nightly_avg for m in metrics if m.hrv.nightly_avg is not None
    ]
    return HrvPatternWindow(
        distribution=_compute_hrv_distribution(nightly_vals, selected_nightly),
        day_of_week=_compute_day_of_week(metrics),
    )


def _compute_pattern_windows(
    metrics: list[DailyMetric],
    selected_nightly: float | None,
) -> dict[str, HrvPatternWindow]:
    """Pre-compute pattern stats for each time window."""
    return compute_windows(
        metrics,
        lambda subset: _compute_pattern_window(subset, selected_nightly),
    )


def load_hrv_analysis(repo: BiometricReadRepository) -> HrvAnalysisResponse:
    """Load daily metrics and compute HRV analysis features (cached)."""
    return cache.cached(cache.HRV_ANALYSIS, lambda: _compute_hrv_analysis(repo))


def _compute_hrv_analysis(repo: BiometricReadRepository) -> HrvAnalysisResponse:
    metrics = repo.load_daily_metrics()
    selected_nightly: float | None = None
    if metrics and metrics[-1].hrv.nightly_avg is not None:
        selected_nightly = metrics[-1].hrv.nightly_avg
    return HrvAnalysisResponse(
        nightly_trend=_compute_nightly_hrv_trend(metrics),
        weekly_boxplots=_compute_weekly_hrv_boxplots(metrics),
        pattern_windows=_compute_pattern_windows(metrics, selected_nightly),
    )
