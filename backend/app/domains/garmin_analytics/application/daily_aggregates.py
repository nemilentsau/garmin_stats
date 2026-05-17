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
        days=[metric.date for metric in metrics],
        daily=metrics,
        period_windows=load_windowed_period_summary(repo),
    )


def get_heart_rate_daily(repo: BiometricReadRepository) -> HeartRateDailyResponse:
    """Return daily heart-rate rows plus heart-rate period summaries."""
    metrics = repo.load_daily_metrics()
    return HeartRateDailyResponse(
        days=_days(metrics),
        daily=[
            HeartRateDailyPoint(
                date=metric.date,
                utc_offset_hours=metric.utc_offset_hours,
                heart_rate=metric.heart_rate,
            )
            for metric in metrics
        ],
        period_windows=_window_field(repo, lambda summary: summary.heart_rate),
    )


def get_hrv_daily(repo: BiometricReadRepository) -> HrvDailyResponse:
    """Return daily HRV rows plus HRV period summaries."""
    metrics = repo.load_daily_metrics()
    return HrvDailyResponse(
        days=_days(metrics),
        daily=[
            HrvDailyPoint(
                date=metric.date,
                utc_offset_hours=metric.utc_offset_hours,
                hrv=metric.hrv,
            )
            for metric in metrics
        ],
        period_windows=_window_field(repo, lambda summary: summary.hrv),
    )


def get_sleep_daily(repo: BiometricReadRepository) -> SleepDailyResponse:
    """Return daily sleep rows plus sleep period summaries."""
    metrics = repo.load_daily_metrics()
    return SleepDailyResponse(
        days=_days(metrics),
        daily=[
            SleepDailyPoint(
                date=metric.date,
                utc_offset_hours=metric.utc_offset_hours,
                sleep=metric.sleep,
            )
            for metric in metrics
        ],
        period_windows=_window_field(repo, lambda summary: summary.sleep),
    )


def get_stress_daily(repo: BiometricReadRepository) -> StressDailyResponse:
    """Return daily stress rows plus stress period summaries."""
    metrics = repo.load_daily_metrics()
    return StressDailyResponse(
        days=_days(metrics),
        daily=[
            StressDailyPoint(
                date=metric.date,
                utc_offset_hours=metric.utc_offset_hours,
                stress=metric.stress,
            )
            for metric in metrics
        ],
        period_windows=_window_field(repo, lambda summary: summary.stress),
    )


def get_respiration_daily(repo: BiometricReadRepository) -> RespirationDailyResponse:
    """Return daily respiration rows plus respiration period summaries."""
    metrics = repo.load_daily_metrics()
    return RespirationDailyResponse(
        days=_days(metrics),
        daily=[
            RespirationDailyPoint(
                date=metric.date,
                utc_offset_hours=metric.utc_offset_hours,
                respiration=metric.respiration,
            )
            for metric in metrics
        ],
        period_windows=_window_field(repo, lambda summary: summary.respiration),
    )


def get_spo2_daily(repo: BiometricReadRepository) -> SpO2DailyResponse:
    """Return daily pulse-ox rows plus pulse-ox period summaries."""
    metrics = repo.load_daily_metrics()
    return SpO2DailyResponse(
        days=_days(metrics),
        daily=[
            SpO2DailyPoint(
                date=metric.date,
                utc_offset_hours=metric.utc_offset_hours,
                spo2=metric.spo2,
            )
            for metric in metrics
        ],
        period_windows=_window_field(repo, lambda summary: summary.spo2),
    )


def get_skin_temp_daily(repo: BiometricReadRepository) -> SkinTempDailyResponse:
    """Return daily skin-temperature rows plus skin-temperature period summaries."""
    metrics = repo.load_daily_metrics()
    return SkinTempDailyResponse(
        days=_days(metrics),
        daily=[
            SkinTempDailyPoint(
                date=metric.date,
                utc_offset_hours=metric.utc_offset_hours,
                skin_temp=metric.skin_temp,
            )
            for metric in metrics
        ],
        period_windows=_window_field(repo, lambda summary: summary.skin_temp),
    )


def get_body_battery_daily(repo: BiometricReadRepository) -> BodyBatteryDailyResponse:
    """Return daily Body Battery rows plus Body Battery period summaries."""
    metrics = repo.load_daily_metrics()
    return BodyBatteryDailyResponse(
        days=_days(metrics),
        daily=[
            BodyBatteryDailyPoint(
                date=metric.date,
                utc_offset_hours=metric.utc_offset_hours,
                body_battery=metric.body_battery,
            )
            for metric in metrics
        ],
        period_windows=_window_field(repo, lambda summary: summary.body_battery),
    )


def load_windowed_period_summary(
    repo: BiometricReadRepository,
) -> dict[str, PeriodSummary]:
    """Compute standard period summaries for the daily metric response."""
    return cache.cached(
        cache.WINDOWED_PERIOD,
        lambda: compute_windows(_reconstruct_day_data(repo), compute_period_summary),
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
