"""Transitional insight use cases for mixed route modules."""

from app.models import HrvAnalysisResponse, HrvInsightsResponse, SleepAnalysisResponse
from app.services.hrv import load_hrv_insights as _load_hrv_insights
from app.services.hrv_analysis import load_hrv_analysis as _load_hrv_analysis
from app.services.sleep_analysis import load_sleep_analysis as _load_sleep_analysis


def get_sleep_analysis() -> SleepAnalysisResponse:
    return _load_sleep_analysis()


def get_hrv_analysis() -> HrvAnalysisResponse:
    return _load_hrv_analysis()


def get_hrv_insights(date: str | None = None) -> HrvInsightsResponse:
    return _load_hrv_insights(date)
