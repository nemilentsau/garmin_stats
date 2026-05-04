"""Transitional insight use cases for Garmin analytics routes."""

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
from app.services.body_battery_analysis import (
    load_body_battery_analysis as _load_body_battery_analysis,
)
from app.services.heart_rate import load_heart_rate_insights as _load_heart_rate_insights
from app.services.heart_rate_analysis import (
    load_heart_rate_analysis as _load_heart_rate_analysis,
)
from app.services.heart_rate_analysis import load_hr_distribution as _load_hr_distribution
from app.services.hrv import load_hrv_insights as _load_hrv_insights
from app.services.hrv_analysis import load_hrv_analysis as _load_hrv_analysis
from app.services.sleep_analysis import load_sleep_analysis as _load_sleep_analysis
from app.services.stress_analysis import load_stress_analysis as _load_stress_analysis


def get_sleep_analysis() -> SleepAnalysisResponse:
    return _load_sleep_analysis()


def get_hrv_analysis() -> HrvAnalysisResponse:
    return _load_hrv_analysis()


def get_hrv_insights(date: str | None = None) -> HrvInsightsResponse:
    return _load_hrv_insights(date)


def get_heart_rate_insights(date: str | None = None) -> HeartRateInsightsResponse:
    return _load_heart_rate_insights(date)


def get_heart_rate_analysis() -> HeartRateAnalysisResponse:
    return _load_heart_rate_analysis()


def get_hr_distribution(date: str) -> HRDistributionResponse:
    return _load_hr_distribution(date)


def get_stress_analysis() -> StressAnalysisResponse:
    return _load_stress_analysis()


def get_body_battery_analysis() -> BodyBatteryAnalysisResponse:
    return _load_body_battery_analysis()
