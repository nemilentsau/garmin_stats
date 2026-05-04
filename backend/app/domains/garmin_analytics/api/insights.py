"""Insight and analysis routes for Garmin analytics."""

from fastapi import APIRouter, Query

from app.bootstrap.container import build_container
from app.domains.garmin_analytics.application import insights as insights_uc
from app.models import (
    BodyBatteryAnalysisResponse,
    HeartRateAnalysisResponse,
    HeartRateInsightsResponse,
    HRDistributionResponse,
    StressAnalysisResponse,
)

heart_rate_router = APIRouter(prefix="/api/heart-rate", tags=["heart-rate"])
stress_router = APIRouter(prefix="/api/stress", tags=["stress"])
body_battery_router = APIRouter(prefix="/api/body-battery", tags=["body-battery"])


@heart_rate_router.get("/insights", response_model=HeartRateInsightsResponse)
def get_heart_rate_insights(
    date: str | None = Query(None, description="Day (YYYY-MM-DD), defaults to latest day"),
):
    """Return backend-derived heart-rate insights for UI rendering."""
    return insights_uc.get_heart_rate_insights(
        build_container().garmin_biometrics_repo,
        date,
    )


@heart_rate_router.get("/analysis", response_model=HeartRateAnalysisResponse)
def get_heart_rate_analysis():
    """Return period-level heart-rate analysis (circadian, sleeping HR, resting trend, boxplots)."""
    return insights_uc.get_heart_rate_analysis(build_container().garmin_biometrics_repo)


@heart_rate_router.get("/distribution", response_model=HRDistributionResponse)
def get_hr_distribution(
    date: str = Query(..., description="Day (YYYY-MM-DD)"),
):
    """Return heart-rate histogram for a single day."""
    return insights_uc.get_hr_distribution(build_container().garmin_biometrics_repo, date)


@stress_router.get("/analysis", response_model=StressAnalysisResponse)
def get_stress_analysis():
    """Return period-level stress analysis (avg trend, weekly boxplots)."""
    return insights_uc.get_stress_analysis(build_container().garmin_biometrics_repo)


@body_battery_router.get("/analysis", response_model=BodyBatteryAnalysisResponse)
def get_body_battery_analysis():
    """Return period-level body battery analysis (trend, weekly boxplots)."""
    return insights_uc.get_body_battery_analysis(build_container().garmin_biometrics_repo)
