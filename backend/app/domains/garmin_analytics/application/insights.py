"""Transitional insight use cases for Garmin analytics routes."""

from app.domains.garmin_analytics.application import (
    analysis,
)
from app.domains.garmin_analytics.application.dependencies import BiometricReadRepository
from app.domains.garmin_analytics.contracts import (
    BodyBatteryAnalysisResponse,
    HeartRateAnalysisResponse,
    HeartRateInsightsResponse,
    HRDistributionResponse,
    HrvAnalysisResponse,
    HrvInsightsResponse,
    SleepAnalysisResponse,
    StressAnalysisResponse,
)
from app.domains.garmin_analytics.domain.insights.heart_rate import (
    compute_heart_rate_insights,
)
from app.domains.garmin_analytics.domain.insights.hrv import compute_hrv_insights


def get_sleep_analysis(repo: BiometricReadRepository) -> SleepAnalysisResponse:
    return analysis.load_sleep_analysis(repo)


def get_hrv_analysis(repo: BiometricReadRepository) -> HrvAnalysisResponse:
    return analysis.load_hrv_analysis(repo)


def get_hrv_insights(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> HrvInsightsResponse:
    metrics = repo.load_daily_metrics()
    if not metrics:
        raise LookupError("No HRV data available")

    selected_date = date or metrics[-1].date
    day_rows = repo.load_hrv(selected_date)
    return compute_hrv_insights(metrics, selected_date, day_rows)


def get_heart_rate_insights(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> HeartRateInsightsResponse:
    metrics = repo.load_daily_metrics()
    if not metrics:
        raise LookupError("No heart-rate data available")

    selected_date = date or metrics[-1].date
    wellness_days = repo.load_wellness(selected_date)
    return compute_heart_rate_insights(metrics, selected_date, wellness_days)


def get_heart_rate_analysis(repo: BiometricReadRepository) -> HeartRateAnalysisResponse:
    return analysis.load_heart_rate_analysis(repo)


def get_hr_distribution(
    repo: BiometricReadRepository,
    date: str,
) -> HRDistributionResponse:
    return analysis.load_hr_distribution(repo, date)


def get_stress_analysis(repo: BiometricReadRepository) -> StressAnalysisResponse:
    return analysis.load_stress_analysis(repo)


def get_body_battery_analysis(
    repo: BiometricReadRepository,
) -> BodyBatteryAnalysisResponse:
    return analysis.load_body_battery_analysis(repo)
