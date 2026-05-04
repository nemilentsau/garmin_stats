"""Sleep analysis calculations for Garmin analytics."""

from app.domains.garmin_analytics.application.ports import BiometricReadRepository
from app.infra import cache
from app.models import (
    DailyMetric,
    SleepAnalysisResponse,
    SleepTrendPoint,
    WeeklySleepBox,
)
from app.stats import group_by_iso_week, safe_percentile, trailing_ma7


def _compute_sleep_trend(
    metrics: list[DailyMetric],
) -> list[SleepTrendPoint]:
    score_values: list[float | None] = [
        float(m.sleep.score) if m.sleep.score is not None else None
        for m in metrics
    ]
    ma7_values = trailing_ma7(score_values)

    return [
        SleepTrendPoint(
            date=m.date,
            score=m.sleep.score,
            deep_score=m.sleep.deep_score,
            rem_score=m.sleep.rem_score,
            ma7=ma7_values[i],
        )
        for i, m in enumerate(metrics)
    ]


def _compute_weekly_sleep_boxplots(
    metrics: list[DailyMetric],
) -> list[WeeklySleepBox]:
    weeks = group_by_iso_week(
        metrics, lambda m: float(m.sleep.score) if m.sleep.score is not None else None
    )
    result: list[WeeklySleepBox] = []
    for week_key in sorted(weeks):
        vals = sorted(weeks[week_key])
        result.append(
            WeeklySleepBox(
                iso_week=week_key,
                min_score=float(vals[0]),
                q1_score=safe_percentile(vals, 25),
                median_score=safe_percentile(vals, 50),
                q3_score=safe_percentile(vals, 75),
                max_score=float(vals[-1]),
                day_count=len(vals),
            )
        )
    return result


def load_sleep_analysis(repo: BiometricReadRepository) -> SleepAnalysisResponse:
    return cache.cached(cache.SLEEP_ANALYSIS, lambda: _compute_sleep_analysis(repo))


def _compute_sleep_analysis(repo: BiometricReadRepository) -> SleepAnalysisResponse:
    metrics = repo.load_daily_metrics()
    return SleepAnalysisResponse(
        score_trend=_compute_sleep_trend(metrics),
        weekly_boxplots=_compute_weekly_sleep_boxplots(metrics),
    )
