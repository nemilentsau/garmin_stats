"""Daily aggregate read use cases for Garmin analytics.

This module returns the persisted daily aggregate mart and computes standard
period windows from raw day tables. Period summaries are recomputed from raw
readings so they do not become averages of daily aggregates.
"""

from app.domains.garmin_analytics.application.dependencies import BiometricReadRepository
from app.domains.garmin_analytics.contracts import (
    DailyAggregatesResponse,
    DayData,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
    PeriodSummary,
)
from app.domains.garmin_analytics.domain.aggregates.period import compute_period_summary
from app.domains.garmin_analytics.domain.primitives.windows import compute_windows
from app.infra import cache


def get_daily_aggregates(
    repo: BiometricReadRepository,
) -> DailyAggregatesResponse:
    metrics = repo.load_daily_metrics()
    return DailyAggregatesResponse(
        days=[metric.date for metric in metrics],
        daily=metrics,
        period_windows=load_windowed_period_summary(repo),
    )


def load_windowed_period_summary(
    repo: BiometricReadRepository,
) -> dict[str, PeriodSummary]:
    """Compute standard period summaries for the daily aggregate response."""
    return cache.cached(
        cache.WINDOWED_PERIOD,
        lambda: compute_windows(_reconstruct_day_data(repo), compute_period_summary),
    )


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
