"""Transitional insight use cases for Garmin analytics routes."""

from app.domains.garmin_analytics.application import (
    body_battery_analysis,
    heart_rate,
    heart_rate_analysis,
    hrv,
    hrv_analysis,
    sleep_analysis,
    stress_analysis,
)
from app.domains.garmin_analytics.application.ports import BiometricReadRepository
from app.models import (
    BodyBatteryAnalysisResponse,
    HeartRateAnalysisResponse,
    HeartRateInsightsResponse,
    HRDistributionResponse,
    HrvAnalysisResponse,
    HrvInsightsResponse,
    SleepAnalysisResponse,
    StressAnalysisResponse,
)


def get_sleep_analysis(repo: BiometricReadRepository) -> SleepAnalysisResponse:
    return sleep_analysis.load_sleep_analysis(repo)


def get_hrv_analysis(repo: BiometricReadRepository) -> HrvAnalysisResponse:
    return hrv_analysis.load_hrv_analysis(repo)


def get_hrv_insights(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> HrvInsightsResponse:
    return hrv.load_hrv_insights(repo, date)


def get_heart_rate_insights(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> HeartRateInsightsResponse:
    return heart_rate.load_heart_rate_insights(repo, date)


def get_heart_rate_analysis(repo: BiometricReadRepository) -> HeartRateAnalysisResponse:
    return heart_rate_analysis.load_heart_rate_analysis(repo)


def get_hr_distribution(
    repo: BiometricReadRepository,
    date: str,
) -> HRDistributionResponse:
    return heart_rate_analysis.load_hr_distribution(repo, date)


def get_stress_analysis(repo: BiometricReadRepository) -> StressAnalysisResponse:
    return stress_analysis.load_stress_analysis(repo)


def get_body_battery_analysis(
    repo: BiometricReadRepository,
) -> BodyBatteryAnalysisResponse:
    return body_battery_analysis.load_body_battery_analysis(repo)
