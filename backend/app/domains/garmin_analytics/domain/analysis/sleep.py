"""Sleep analysis calculations for Garmin analytics."""

from app.domains.garmin_analytics.contracts import (
    DailyMetric,
    SleepAnalysisResponse,
    SleepTrendPoint,
    WeeklySleepBox,
)
from app.domains.garmin_analytics.domain.primitives.numeric import optional_float
from app.domains.garmin_analytics.domain.primitives.trends import (
    trailing_ma7,
    weekly_five_number_summaries,
)


def compute_sleep_trend(
    metrics: list[DailyMetric],
) -> list[SleepTrendPoint]:
    score_values = [optional_float(m.sleep.score) for m in metrics]
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


def compute_weekly_sleep_boxplots(
    metrics: list[DailyMetric],
) -> list[WeeklySleepBox]:
    summaries = weekly_five_number_summaries(
        metrics,
        lambda m: optional_float(m.sleep.score),
    )
    return [
        WeeklySleepBox(
            iso_week=summary.iso_week,
            min_score=summary.min,
            q1_score=summary.q1,
            median_score=summary.median,
            q3_score=summary.q3,
            max_score=summary.max,
            day_count=summary.count,
        )
        for summary in summaries
    ]


def compute_sleep_analysis(metrics: list[DailyMetric]) -> SleepAnalysisResponse:
    return SleepAnalysisResponse(
        score_trend=compute_sleep_trend(metrics),
        weekly_boxplots=compute_weekly_sleep_boxplots(metrics),
    )
