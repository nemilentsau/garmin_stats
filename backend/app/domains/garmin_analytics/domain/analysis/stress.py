"""Stress analysis calculations for Garmin analytics."""

from app.domains.garmin_analytics.contracts import (
    DailyMetric,
    StressAnalysisResponse,
    StressTrendPoint,
    WeeklyStressBox,
)
from app.domains.garmin_analytics.domain.primitives.trends import (
    trailing_ma7,
    weekly_five_number_summaries,
)


def compute_stress_trend(
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


def compute_weekly_stress_boxplots(
    metrics: list[DailyMetric],
) -> list[WeeklyStressBox]:
    summaries = weekly_five_number_summaries(metrics, lambda m: m.stress.avg)
    return [
        WeeklyStressBox(
            iso_week=summary.iso_week,
            min_avg=summary.min,
            q1_avg=summary.q1,
            median_avg=summary.median,
            q3_avg=summary.q3,
            max_avg=summary.max,
            day_count=summary.count,
        )
        for summary in summaries
    ]


def compute_stress_analysis(metrics: list[DailyMetric]) -> StressAnalysisResponse:
    return StressAnalysisResponse(
        avg_trend=compute_stress_trend(metrics),
        weekly_boxplots=compute_weekly_stress_boxplots(metrics),
    )
