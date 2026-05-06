"""Stress analysis calculations for Garmin analytics."""

from app.domains.garmin_analytics.application.ports import BiometricReadRepository
from app.infra import cache
from app.models import (
    DailyMetric,
    StressAnalysisResponse,
    StressTrendPoint,
    WeeklyStressBox,
)

from .numeric import safe_percentile
from .trends import group_by_iso_week, trailing_ma7


def _compute_stress_trend(
    metrics: list[DailyMetric],
) -> list[StressTrendPoint]:
    avg_values: list[float | None] = [m.stress.avg for m in metrics]
    ma7_values = trailing_ma7(avg_values)

    return [
        StressTrendPoint(
            date=m.date,
            avg=avg_values[i],
            ma7=ma7_values[i],
        )
        for i, m in enumerate(metrics)
    ]


def _compute_weekly_stress_boxplots(
    metrics: list[DailyMetric],
) -> list[WeeklyStressBox]:
    weeks = group_by_iso_week(metrics, lambda m: m.stress.avg)
    result: list[WeeklyStressBox] = []
    for week_key in sorted(weeks):
        vals = sorted(weeks[week_key])
        result.append(
            WeeklyStressBox(
                iso_week=week_key,
                min_avg=float(vals[0]),
                q1_avg=safe_percentile(vals, 25),
                median_avg=safe_percentile(vals, 50),
                q3_avg=safe_percentile(vals, 75),
                max_avg=float(vals[-1]),
                day_count=len(vals),
            )
        )
    return result


def load_stress_analysis(repo: BiometricReadRepository) -> StressAnalysisResponse:
    return cache.cached(cache.STRESS_ANALYSIS, lambda: _compute_stress_analysis(repo))


def _compute_stress_analysis(repo: BiometricReadRepository) -> StressAnalysisResponse:
    metrics = repo.load_daily_metrics()
    return StressAnalysisResponse(
        avg_trend=_compute_stress_trend(metrics),
        weekly_boxplots=_compute_weekly_stress_boxplots(metrics),
    )
