"""Daily metric read use cases for Garmin analytics.

This module returns the persisted daily metric mart and computes standard
period windows from raw day tables. Period summaries are recomputed from raw
readings so they do not become averages of daily metric rows.
"""

from collections.abc import Callable

from app.domains.garmin_analytics.application.dependencies import BiometricReadRepository
from app.domains.garmin_analytics.contracts import (
    BodyBatteryDailyPoint,
    BodyBatteryDailyResponse,
    DailyAggregatesResponse,
    HeartRateDailyPoint,
    HeartRateDailyResponse,
    HrvDailyPoint,
    HrvDailyResponse,
    PeriodSummary,
    RespirationDailyPoint,
    RespirationDailyResponse,
    SkinTempDailyPoint,
    SkinTempDailyResponse,
    SleepDailyPoint,
    SleepDailyResponse,
    SpO2DailyPoint,
    SpO2DailyResponse,
    StressDailyPoint,
    StressDailyResponse,
)
from app.domains.garmin_analytics.domain.aggregates.period import compute_period_summary
from app.domains.garmin_analytics.domain.primitives.windows import compute_windows
from app.domains.garmin_health.contracts import (
    DailyMetric,
    DayData,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
)
from app.infra import cache


def get_daily_aggregates(
    repo: BiometricReadRepository,
) -> DailyAggregatesResponse:
    """Return persisted daily metrics plus standard period summaries."""
    metrics = repo.load_daily_metrics()
    return DailyAggregatesResponse(
        days=_days(metrics),
        daily=metrics,
        period_windows=load_windowed_period_summary(repo),
    )


def get_heart_rate_daily(repo: BiometricReadRepository) -> HeartRateDailyResponse:
    return _build_daily(repo, HeartRateDailyPoint, HeartRateDailyResponse, "heart_rate")


def get_hrv_daily(repo: BiometricReadRepository) -> HrvDailyResponse:
    return _build_daily(repo, HrvDailyPoint, HrvDailyResponse, "hrv")


def get_sleep_daily(repo: BiometricReadRepository) -> SleepDailyResponse:
    return _build_daily(repo, SleepDailyPoint, SleepDailyResponse, "sleep")


def get_stress_daily(repo: BiometricReadRepository) -> StressDailyResponse:
    return _build_daily(repo, StressDailyPoint, StressDailyResponse, "stress")


def get_respiration_daily(repo: BiometricReadRepository) -> RespirationDailyResponse:
    return _build_daily(repo, RespirationDailyPoint, RespirationDailyResponse, "respiration")


def get_spo2_daily(repo: BiometricReadRepository) -> SpO2DailyResponse:
    return _build_daily(repo, SpO2DailyPoint, SpO2DailyResponse, "spo2")


def get_skin_temp_daily(repo: BiometricReadRepository) -> SkinTempDailyResponse:
    return _build_daily(repo, SkinTempDailyPoint, SkinTempDailyResponse, "skin_temp")


def get_body_battery_daily(repo: BiometricReadRepository) -> BodyBatteryDailyResponse:
    return _build_daily(repo, BodyBatteryDailyPoint, BodyBatteryDailyResponse, "body_battery")


def load_windowed_period_summary(
    repo: BiometricReadRepository,
) -> dict[str, PeriodSummary]:
    """Compute standard period summaries for the daily metric response."""
    return cache.cached(
        cache.WINDOWED_PERIOD,
        lambda: compute_windows(_reconstruct_day_data(repo), compute_period_summary),
    )


def _build_daily[Point, Response](
    repo: BiometricReadRepository,
    point_cls: Callable[..., Point],
    response_cls: Callable[..., Response],
    field: str,
) -> Response:
    """Project one metric field out of the daily mart and matching period windows."""
    metrics = repo.load_daily_metrics()
    return response_cls(
        days=_days(metrics),
        daily=[
            point_cls(
                date=metric.date,
                utc_offset_hours=metric.utc_offset_hours,
                **{field: getattr(metric, field)},
            )
            for metric in metrics
        ],
        period_windows=_window_field(repo, lambda summary: getattr(summary, field)),
    )


def _days(metrics: list[DailyMetric]) -> list[str]:
    return [metric.date for metric in metrics]


def _window_field[PeriodWindow](
    repo: BiometricReadRepository,
    select: Callable[[PeriodSummary], PeriodWindow],
) -> dict[str, PeriodWindow]:
    return {
        label: select(summary)
        for label, summary in load_windowed_period_summary(repo).items()
    }


def _reconstruct_day_data(repo: BiometricReadRepository) -> list[DayData]:
    """Rejoin persisted day-table slices into the raw shape expected by aggregates."""
    wellness_by_date = {day.date: day for day in repo.load_wellness()}
    sleep_by_date = {day.date: day for day in repo.load_sleep()}
    hrv_by_date = {day.date: day for day in repo.load_hrv()}
    skin_by_date = {day.date: day for day in repo.load_skin_temp()}

    all_dates = sorted(
        wellness_by_date.keys()
        | sleep_by_date.keys()
        | hrv_by_date.keys()
        | skin_by_date.keys()
    )

    return [
        DayData(
            date=date,
            wellness=wellness_by_date.get(date, DayWellness(date=date)),
            sleep=sleep_by_date.get(date, DaySleep(date=date)),
            hrv=hrv_by_date.get(date, DayHrv(date=date)),
            skin_temp=skin_by_date.get(date, DaySkinTemp(date=date)),
        )
        for date in all_dates
    ]
