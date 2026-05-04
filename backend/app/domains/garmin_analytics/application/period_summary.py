"""Windowed period summaries for Garmin biometric data."""

from app.domains.garmin_analytics.application.ports import BiometricReadRepository
from app.domains.garmin_analytics.domain.windows import compute_windows
from app.infra import cache
from app.models import (
    DayData,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
    PeriodSummary,
)
from app.stats import compute_period_summary


def load_windowed_period_summary(
    repo: BiometricReadRepository,
) -> dict[str, PeriodSummary]:
    """Compute standard period summaries from current biometric tables."""
    return cache.cached(
        cache.WINDOWED_PERIOD,
        lambda: compute_windows(_reconstruct_day_data(repo), compute_period_summary),
    )


def _reconstruct_day_data(repo: BiometricReadRepository) -> list[DayData]:
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
