"""Body Battery analysis: daily min/max trend with 7-day MA, weekly boxplots."""

from ..infra import cache
from ..infra.database import load_daily_metrics
from ..models import (
    BodyBatteryAnalysisResponse,
    BodyBatteryTrendPoint,
    DailyMetric,
    WeeklyBodyBatteryBox,
)
from ..stats import group_by_iso_week, safe_percentile, trailing_ma7

BODY_BATTERY_ANALYSIS = "body_battery_analysis"


def _compute_body_battery_trend(
    metrics: list[DailyMetric],
) -> list[BodyBatteryTrendPoint]:
    min_values: list[float | None] = [
        float(m.body_battery.min) if m.body_battery.min is not None else None
        for m in metrics
    ]
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


def _compute_weekly_body_battery_boxplots(
    metrics: list[DailyMetric],
) -> list[WeeklyBodyBatteryBox]:
    weeks = group_by_iso_week(
        metrics, lambda m: float(m.body_battery.min) if m.body_battery.min is not None else None
    )
    result: list[WeeklyBodyBatteryBox] = []
    for week_key in sorted(weeks):
        vals = sorted(weeks[week_key])
        result.append(
            WeeklyBodyBatteryBox(
                iso_week=week_key,
                min_val=float(vals[0]),
                q1_val=safe_percentile(vals, 25),
                median_val=safe_percentile(vals, 50),
                q3_val=safe_percentile(vals, 75),
                max_val=float(vals[-1]),
                day_count=len(vals),
            )
        )
    return result


def load_body_battery_analysis() -> BodyBatteryAnalysisResponse:
    return cache.cached(BODY_BATTERY_ANALYSIS, _compute_body_battery_analysis)


def _compute_body_battery_analysis() -> BodyBatteryAnalysisResponse:
    metrics = load_daily_metrics()
    return BodyBatteryAnalysisResponse(
        trend=_compute_body_battery_trend(metrics),
        weekly_boxplots=_compute_weekly_body_battery_boxplots(metrics),
    )
