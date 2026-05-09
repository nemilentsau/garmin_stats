"""HTTP routes for Garmin analytics.

Routes bind FastAPI request/response metadata to application use cases. They
should not own repository queries, cache policy, or metric calculations.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.bootstrap.container import build_container
from app.domains.garmin_analytics.application import (
    daily_aggregates as daily_aggregates_uc,
)
from app.domains.garmin_analytics.application import metric_analysis as metric_analysis_uc
from app.domains.garmin_analytics.application import metric_insights as metric_insights_uc
from app.domains.garmin_analytics.application import raw_biometrics as raw_biometrics_uc
from app.domains.garmin_analytics.application.dashboard import (
    get_dashboard_overview as load_dashboard_overview,
)
from app.domains.garmin_analytics.application.dependencies import BiometricReadRepository
from app.domains.garmin_analytics.contracts import (
    BodyBatteryAnalysisResponse,
    BodyBatteryRawResponse,
    DailyAggregatesResponse,
    DashboardOverviewResponse,
    HeartRateAnalysisResponse,
    HeartRateInsightsResponse,
    HeartRateRawResponse,
    HRDistributionResponse,
    HrvAnalysisResponse,
    HrvInsightsResponse,
    HrvResponse,
    RespirationRawResponse,
    SkinTempResponse,
    SleepAnalysisResponse,
    SleepResponse,
    SpO2RawResponse,
    StressAnalysisResponse,
    StressRawResponse,
)


def get_biometrics_repo() -> BiometricReadRepository:
    """FastAPI dependency yielding the configured biometrics repository."""
    return build_container().garmin_biometrics_repo


BiometricsRepo = Annotated[BiometricReadRepository, Depends(get_biometrics_repo)]


dashboard_router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
sleep_router = APIRouter(prefix="/api/sleep", tags=["sleep"])
hrv_router = APIRouter(prefix="/api/hrv", tags=["hrv"])
skin_temp_router = APIRouter(prefix="/api/skin-temp", tags=["skin-temp"])
daily_aggregates_router = APIRouter(
    prefix="/api/daily-aggregates",
    tags=["daily-aggregates"],
)
heart_rate_router = APIRouter(prefix="/api/heart-rate", tags=["heart-rate"])
stress_router = APIRouter(prefix="/api/stress", tags=["stress"])
body_battery_router = APIRouter(prefix="/api/body-battery", tags=["body-battery"])
respiration_router = APIRouter(prefix="/api/respiration", tags=["respiration"])
pulse_ox_router = APIRouter(prefix="/api/pulse-ox", tags=["pulse-ox"])


@dashboard_router.get("", response_model=DashboardOverviewResponse)
def get_dashboard_overview(repo: BiometricsRepo):
    """Return readiness score and cross-domain correlations."""
    return load_dashboard_overview(repo)


@sleep_router.get("", response_model=SleepResponse)
def get_sleep(
    repo: BiometricsRepo,
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get sleep data (stages, assessment scores)."""
    return raw_biometrics_uc.get_sleep(repo, date=date)


@sleep_router.get("/analysis", response_model=SleepAnalysisResponse)
def get_sleep_analysis(repo: BiometricsRepo):
    """Return period-level sleep analysis (score trend, weekly boxplots)."""
    return metric_analysis_uc.load_sleep_analysis(repo)


@hrv_router.get("", response_model=HrvResponse)
def get_hrv(
    repo: BiometricsRepo,
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get HRV data (values, summaries)."""
    return raw_biometrics_uc.get_hrv(repo, date=date)


@hrv_router.get("/analysis", response_model=HrvAnalysisResponse)
def get_hrv_analysis(repo: BiometricsRepo):
    """Return pre-computed HRV analysis (nightly trend with 7d MA, weekly boxplots)."""
    return metric_analysis_uc.load_hrv_analysis(repo)


@hrv_router.get("/insights", response_model=HrvInsightsResponse)
def get_hrv_insights(
    repo: BiometricsRepo,
    date: str | None = Query(None, description="Day (YYYY-MM-DD), defaults to latest day"),
):
    """Return backend-derived HRV insights for UI rendering."""
    return metric_insights_uc.get_hrv_insights(repo, date)


@skin_temp_router.get("", response_model=SkinTempResponse)
def get_skin_temp(
    repo: BiometricsRepo,
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get skin temperature data."""
    return raw_biometrics_uc.get_skin_temp(repo, date=date)


@daily_aggregates_router.get("", response_model=DailyAggregatesResponse)
def get_daily_agg(repo: BiometricsRepo):
    """Get per-day aggregate stats for all metrics, plus windowed period summaries."""
    return daily_aggregates_uc.get_daily_aggregates(repo)


@heart_rate_router.get("/insights", response_model=HeartRateInsightsResponse)
def get_heart_rate_insights(
    repo: BiometricsRepo,
    date: str | None = Query(None, description="Day (YYYY-MM-DD), defaults to latest day"),
):
    """Return backend-derived heart-rate insights for UI rendering."""
    return metric_insights_uc.get_heart_rate_insights(repo, date)


@heart_rate_router.get("/raw", response_model=HeartRateRawResponse)
def get_heart_rate_raw(
    repo: BiometricsRepo,
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get raw heart-rate and resting-heart-rate readings."""
    return raw_biometrics_uc.get_heart_rate_raw(repo, date=date)


@heart_rate_router.get("/analysis", response_model=HeartRateAnalysisResponse)
def get_heart_rate_analysis(repo: BiometricsRepo):
    """Return period-level heart-rate analysis (circadian, sleeping HR, resting trend, boxplots)."""
    return metric_analysis_uc.load_heart_rate_analysis(repo)


@heart_rate_router.get("/distribution", response_model=HRDistributionResponse)
def get_hr_distribution(
    repo: BiometricsRepo,
    date: str = Query(..., description="Day (YYYY-MM-DD)"),
):
    """Return heart-rate histogram for a single day."""
    return metric_analysis_uc.load_hr_distribution(repo, date)


@stress_router.get("/raw", response_model=StressRawResponse)
def get_stress_raw(
    repo: BiometricsRepo,
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get raw stress readings."""
    return raw_biometrics_uc.get_stress_raw(repo, date=date)


@stress_router.get("/analysis", response_model=StressAnalysisResponse)
def get_stress_analysis(repo: BiometricsRepo):
    """Return period-level stress analysis (avg trend, weekly boxplots)."""
    return metric_analysis_uc.load_stress_analysis(repo)


@body_battery_router.get("/raw", response_model=BodyBatteryRawResponse)
def get_body_battery_raw(
    repo: BiometricsRepo,
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get raw body-battery readings."""
    return raw_biometrics_uc.get_body_battery_raw(repo, date=date)


@body_battery_router.get("/analysis", response_model=BodyBatteryAnalysisResponse)
def get_body_battery_analysis(repo: BiometricsRepo):
    """Return period-level body battery analysis (trend, weekly boxplots)."""
    return metric_analysis_uc.load_body_battery_analysis(repo)


@respiration_router.get("/raw", response_model=RespirationRawResponse)
def get_respiration_raw(
    repo: BiometricsRepo,
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get raw respiration readings."""
    return raw_biometrics_uc.get_respiration_raw(repo, date=date)


@pulse_ox_router.get("/raw", response_model=SpO2RawResponse)
def get_pulse_ox_raw(
    repo: BiometricsRepo,
    date: str | None = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    """Get raw pulse-ox readings."""
    return raw_biometrics_uc.get_spo2_raw(repo, date=date)
