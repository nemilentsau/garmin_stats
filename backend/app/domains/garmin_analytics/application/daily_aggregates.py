"""Daily aggregate read use cases for Garmin analytics."""

from app.domains.garmin_analytics.application.dependencies import BiometricReadRepository
from app.domains.garmin_analytics.application.periods import load_windowed_period_summary
from app.domains.garmin_analytics.contracts import DailyAggregatesResponse


def get_daily_aggregates(
    repo: BiometricReadRepository,
) -> DailyAggregatesResponse:
    metrics = repo.load_daily_metrics()
    return DailyAggregatesResponse(
        days=[metric.date for metric in metrics],
        daily=metrics,
        period_windows=load_windowed_period_summary(repo),
    )
