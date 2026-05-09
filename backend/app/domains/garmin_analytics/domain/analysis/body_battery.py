"""Body Battery analysis calculations for Garmin analytics."""

from app.domains.garmin_analytics.contracts import (
    BodyBatteryAnalysisResponse,
    BodyBatteryTrendPoint,
    WeeklyBodyBatteryBox,
)
from app.domains.garmin_analytics.domain.primitives.trends import (
    trailing_ma7,
    weekly_five_number_summaries,
)
from app.domains.garmin_health.contracts import DailyMetric
from app.utils.numeric import optional_float


def compute_body_battery_trend(
    metrics: list[DailyMetric],
) -> list[BodyBatteryTrendPoint]:
    """Build daily Body Battery min/max trend points with 7-day smoothing."""
    min_values = [optional_float(m.body_battery.min) for m in metrics]
    ma7_min_values = trailing_ma7(min_values)

    return [
        BodyBatteryTrendPoint(
            date=m.date,
            min_val=m.body_battery.min,
            max_val=m.body_battery.max,
            ma7_min=ma7_min_values[i],
        )
        for i, m in enumerate(metrics)
    ]


def compute_weekly_body_battery_boxplots(
    metrics: list[DailyMetric],
) -> list[WeeklyBodyBatteryBox]:
    """Build weekly five-number summaries of daily Body Battery minimums."""
    summaries = weekly_five_number_summaries(
        metrics,
        lambda m: optional_float(m.body_battery.min),
    )
    return [
        WeeklyBodyBatteryBox(
            iso_week=summary.iso_week,
            min_val=summary.min,
            q1_val=summary.q1,
            median_val=summary.median,
            q3_val=summary.q3,
            max_val=summary.max,
            day_count=summary.count,
        )
        for summary in summaries
    ]


def compute_body_battery_analysis(
    metrics: list[DailyMetric],
) -> BodyBatteryAnalysisResponse:
    """Compute Body Battery analysis read model from daily metrics."""
    return BodyBatteryAnalysisResponse(
        trend=compute_body_battery_trend(metrics),
        weekly_boxplots=compute_weekly_body_battery_boxplots(metrics),
    )
