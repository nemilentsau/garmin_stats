"""Selected-day metric insight use cases for Garmin analytics routes.

Use cases resolve the selected day and retrieve the raw rows needed by insight
calculators. Interpretation rules and messages live in `domain.insights`.
"""

from app.domains.garmin_analytics.application.dependencies import BiometricReadRepository
from app.domains.garmin_analytics.contracts import (
    BASELINE_WINDOW_DEFAULT,
    HeartRateInsightsResponse,
    HrvInsightsResponse,
)
from app.domains.garmin_analytics.domain.insights.heart_rate import (
    compute_heart_rate_insights,
)
from app.domains.garmin_analytics.domain.insights.hrv import compute_hrv_insights


def get_hrv_insights(
    repo: BiometricReadRepository,
    date: str | None = None,
    baseline: int = BASELINE_WINDOW_DEFAULT,
) -> HrvInsightsResponse:
    """Return HRV insights for the selected date or latest metric date."""
    metrics = repo.load_daily_metrics()
    if not metrics:
        raise LookupError("No HRV data available")

    selected_date = date or metrics[-1].date
    day_rows = repo.load_hrv(selected_date)
    return compute_hrv_insights(metrics, selected_date, day_rows, window=baseline)


def get_heart_rate_insights(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> HeartRateInsightsResponse:
    """Return heart-rate insights for the selected date or latest metric date."""
    metrics = repo.load_daily_metrics()
    if not metrics:
        raise LookupError("No heart-rate data available")

    selected_date = date or metrics[-1].date
    wellness_days = repo.load_wellness(selected_date)
    return compute_heart_rate_insights(metrics, selected_date, wellness_days)
