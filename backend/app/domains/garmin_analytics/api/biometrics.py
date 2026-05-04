"""Biometric routes for Garmin analytics."""

from fastapi import APIRouter, Query

from app.bootstrap.container import build_container
from app.domains.garmin_analytics.application import biometrics as biometrics_uc
from app.domains.garmin_analytics.application import insights as insights_uc
from app.models import (
    DailyAggregatesResponse,
    HrvAnalysisResponse,
    HrvInsightsResponse,
    HrvResponse,
    SkinTempResponse,
    SleepAnalysisResponse,
    SleepResponse,
    WellnessResponse,
)

wellness_router = APIRouter(prefix="/api/wellness", tags=["wellness"])
sleep_router = APIRouter(prefix="/api/sleep", tags=["sleep"])
hrv_router = APIRouter(prefix="/api/hrv", tags=["hrv"])
skin_temp_router = APIRouter(prefix="/api/skin-temp", tags=["skin-temp"])
daily_aggregates_router = APIRouter(
    prefix="/api/daily-aggregates",
    tags=["daily-aggregates"],
)


@wellness_router.get("", response_model=WellnessResponse)
def get_wellness(
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get wellness data (HR, stress, SpO2, respiration, activity)."""
    return biometrics_uc.get_wellness(build_container().garmin_biometrics_repo, date=date)


@sleep_router.get("", response_model=SleepResponse)
def get_sleep(
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get sleep data (stages, assessment scores)."""
    return biometrics_uc.get_sleep(build_container().garmin_biometrics_repo, date=date)


@sleep_router.get("/analysis", response_model=SleepAnalysisResponse)
def get_sleep_analysis():
    """Return period-level sleep analysis (score trend, weekly boxplots)."""
    return insights_uc.get_sleep_analysis()


@hrv_router.get("", response_model=HrvResponse)
def get_hrv(
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get HRV data (values, summaries)."""
    return biometrics_uc.get_hrv(build_container().garmin_biometrics_repo, date=date)


@hrv_router.get("/analysis", response_model=HrvAnalysisResponse)
def get_hrv_analysis():
    """Return pre-computed HRV analysis (nightly trend with 7d MA, weekly boxplots)."""
    return insights_uc.get_hrv_analysis()


@hrv_router.get("/insights", response_model=HrvInsightsResponse)
def get_hrv_insights(
    date: str | None = Query(None, description="Day (YYYY-MM-DD), defaults to latest day"),
):
    """Return backend-derived HRV insights for UI rendering."""
    return insights_uc.get_hrv_insights(date)


@skin_temp_router.get("", response_model=SkinTempResponse)
def get_skin_temp(
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get skin temperature data."""
    return biometrics_uc.get_skin_temp(build_container().garmin_biometrics_repo, date=date)


@daily_aggregates_router.get("", response_model=DailyAggregatesResponse)
def get_daily_agg():
    """Get per-day aggregate stats for all metrics, plus windowed period summaries."""
    return biometrics_uc.get_daily_aggregates(build_container().garmin_biometrics_repo)
