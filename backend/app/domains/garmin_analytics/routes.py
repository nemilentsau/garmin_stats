"""HTTP routes for Garmin analytics.

Routes bind FastAPI request/response metadata to application use cases. They
should not own repository queries, cache policy, or metric calculations.
"""

from datetime import date as Date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.bootstrap.container import build_container
from app.domains.garmin_analytics.application import (
    daily_aggregates as daily_aggregates_uc,
)
from app.domains.garmin_analytics.application import metric_analysis as metric_analysis_uc
from app.domains.garmin_analytics.application import metric_insights as metric_insights_uc
from app.domains.garmin_analytics.application import raw_biometrics as raw_biometrics_uc
from app.domains.garmin_analytics.application import runs as runs_uc
from app.domains.garmin_analytics.application.dashboard import (
    get_dashboard_overview as load_dashboard_overview,
)
from app.domains.garmin_analytics.application.dependencies import (
    BiometricReadRepository,
    RunsReadRepository,
)
from app.domains.garmin_analytics.contracts import (
    BASELINE_WINDOW_DEFAULT,
    BaselineWindow,
    BodyBatteryAnalysisResponse,
    BodyBatteryDailyResponse,
    BodyBatteryRawResponse,
    DailyAggregatesResponse,
    DashboardOverviewResponse,
    HeartRateAnalysisResponse,
    HeartRateDailyResponse,
    HeartRateInsightsResponse,
    HeartRateRawResponse,
    HRDistributionResponse,
    HrvAnalysisResponse,
    HrvDailyResponse,
    HrvInsightsResponse,
    HrvResponse,
    RespirationDailyResponse,
    RespirationRawResponse,
    RunDetailResponse,
    RunSeriesResponse,
    RunsListResponse,
    SkinTempDailyResponse,
    SkinTempResponse,
    SleepAnalysisResponse,
    SleepDailyResponse,
    SleepResponse,
    SpO2DailyResponse,
    SpO2RawResponse,
    StressAnalysisResponse,
    StressDailyResponse,
    StressRawResponse,
)


def get_biometrics_repo() -> BiometricReadRepository:
    """FastAPI dependency yielding the configured biometrics repository."""
    return build_container().garmin_biometrics_repo


BiometricsRepo = Annotated[BiometricReadRepository, Depends(get_biometrics_repo)]


def get_runs_repo() -> RunsReadRepository:
    """FastAPI dependency yielding the configured runs read repository."""
    return build_container().garmin_runs_repo


RunsRepo = Annotated[RunsReadRepository, Depends(get_runs_repo)]
_HrvBaseline = Annotated[
    BaselineWindow,
    Query(description="Trailing baseline window (days)"),
]
# Single source of truth for the HTTP default — derived from the contract default so changing
# BASELINE_WINDOW_DEFAULT changes the served default too (a module-level singleton, not a call
# in the argument default, which ruff B008 forbids).
_HRV_BASELINE_DEFAULT = BaselineWindow(BASELINE_WINDOW_DEFAULT)
_OptionalFilterDate = Annotated[
    Date | None, Query(description="Filter by date (YYYY-MM-DD)")
]
_OptionalInsightDate = Annotated[
    Date | None, Query(description="Day (YYYY-MM-DD), defaults to latest day")
]
_RequiredDayDate = Annotated[Date, Query(description="Day (YYYY-MM-DD)")]
_RunsFromDate = Annotated[
    Date | None, Query(alias="from", description="YYYY-MM-DD inclusive")
]
_RunsToDate = Annotated[
    Date | None, Query(alias="to", description="YYYY-MM-DD inclusive")
]


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
runs_router = APIRouter(prefix="/api/activities/runs", tags=["runs"])


@dashboard_router.get("", response_model=DashboardOverviewResponse)
def get_dashboard_overview(repo: BiometricsRepo):
    """Return the recovery overview: state, score trajectory, evidence, and health flags."""
    return load_dashboard_overview(repo)


@sleep_router.get("/raw", response_model=SleepResponse)
def get_sleep_raw(
    repo: BiometricsRepo,
    date: _OptionalFilterDate = None,
):
    """Get raw sleep data (stages, assessment scores)."""
    return raw_biometrics_uc.get_sleep(
        repo, date=date.isoformat() if date is not None else None
    )


@sleep_router.get("/analysis", response_model=SleepAnalysisResponse)
def get_sleep_analysis(repo: BiometricsRepo):
    """Return period-level sleep analysis (score trend, weekly boxplots)."""
    return metric_analysis_uc.load_sleep_analysis(repo)


@sleep_router.get("/daily", response_model=SleepDailyResponse)
def get_sleep_daily(repo: BiometricsRepo):
    """Return daily sleep metrics and period summaries."""
    return daily_aggregates_uc.get_sleep_daily(repo)


@hrv_router.get("/raw", response_model=HrvResponse)
def get_hrv_raw(
    repo: BiometricsRepo,
    date: _OptionalFilterDate = None,
):
    """Get raw HRV data (values, summaries)."""
    return raw_biometrics_uc.get_hrv(
        repo, date=date.isoformat() if date is not None else None
    )


@hrv_router.get("/analysis", response_model=HrvAnalysisResponse)
def get_hrv_analysis(
    repo: BiometricsRepo,
    baseline: _HrvBaseline = _HRV_BASELINE_DEFAULT,
):
    """Return pre-computed HRV analysis (nightly trend with 7d MA + trailing band)."""
    return metric_analysis_uc.load_hrv_analysis(repo, baseline=int(baseline))


@hrv_router.get("/daily", response_model=HrvDailyResponse)
def get_hrv_daily(repo: BiometricsRepo):
    """Return daily HRV metrics and period summaries."""
    return daily_aggregates_uc.get_hrv_daily(repo)


@hrv_router.get("/insights", response_model=HrvInsightsResponse)
def get_hrv_insights(
    repo: BiometricsRepo,
    date: _OptionalInsightDate = None,
    baseline: _HrvBaseline = _HRV_BASELINE_DEFAULT,
):
    """Return backend-derived HRV insights for UI rendering."""
    return metric_insights_uc.get_hrv_insights(
        repo,
        date.isoformat() if date is not None else None,
        baseline=int(baseline),
    )


@skin_temp_router.get("/raw", response_model=SkinTempResponse)
def get_skin_temp_raw(
    repo: BiometricsRepo,
    date: _OptionalFilterDate = None,
):
    """Get raw skin-temperature data."""
    return raw_biometrics_uc.get_skin_temp(
        repo, date=date.isoformat() if date is not None else None
    )


@skin_temp_router.get("/daily", response_model=SkinTempDailyResponse)
def get_skin_temp_daily(repo: BiometricsRepo):
    """Return daily skin-temperature metrics and period summaries."""
    return daily_aggregates_uc.get_skin_temp_daily(repo)


@daily_aggregates_router.get("", response_model=DailyAggregatesResponse)
def get_daily_agg(repo: BiometricsRepo):
    """Get per-day aggregate stats for all metrics, plus windowed period summaries."""
    return daily_aggregates_uc.get_daily_aggregates(repo)


@heart_rate_router.get("/insights", response_model=HeartRateInsightsResponse)
def get_heart_rate_insights(
    repo: BiometricsRepo,
    date: _OptionalInsightDate = None,
):
    """Return backend-derived heart-rate insights for UI rendering."""
    return metric_insights_uc.get_heart_rate_insights(
        repo, date.isoformat() if date is not None else None
    )


@heart_rate_router.get("/daily", response_model=HeartRateDailyResponse)
def get_heart_rate_daily(repo: BiometricsRepo):
    """Return daily heart-rate metrics and period summaries."""
    return daily_aggregates_uc.get_heart_rate_daily(repo)


@heart_rate_router.get("/raw", response_model=HeartRateRawResponse)
def get_heart_rate_raw(
    repo: BiometricsRepo,
    date: _OptionalFilterDate = None,
):
    """Get raw heart-rate and resting-heart-rate readings."""
    return raw_biometrics_uc.get_heart_rate_raw(
        repo, date=date.isoformat() if date is not None else None
    )


@heart_rate_router.get("/analysis", response_model=HeartRateAnalysisResponse)
def get_heart_rate_analysis(repo: BiometricsRepo):
    """Return period-level heart-rate analysis (circadian, sleeping HR, resting trend, boxplots)."""
    return metric_analysis_uc.load_heart_rate_analysis(repo)


@heart_rate_router.get("/distribution", response_model=HRDistributionResponse)
def get_hr_distribution(
    repo: BiometricsRepo,
    date: _RequiredDayDate,
):
    """Return heart-rate histogram for a single day."""
    return metric_analysis_uc.load_hr_distribution(repo, date.isoformat())


@stress_router.get("/raw", response_model=StressRawResponse)
def get_stress_raw(
    repo: BiometricsRepo,
    date: _OptionalFilterDate = None,
):
    """Get raw stress readings."""
    return raw_biometrics_uc.get_stress_raw(
        repo, date=date.isoformat() if date is not None else None
    )


@stress_router.get("/daily", response_model=StressDailyResponse)
def get_stress_daily(repo: BiometricsRepo):
    """Return daily stress metrics and period summaries."""
    return daily_aggregates_uc.get_stress_daily(repo)


@stress_router.get("/analysis", response_model=StressAnalysisResponse)
def get_stress_analysis(repo: BiometricsRepo):
    """Return period-level stress analysis (avg trend, weekly boxplots)."""
    return metric_analysis_uc.load_stress_analysis(repo)


@body_battery_router.get("/raw", response_model=BodyBatteryRawResponse)
def get_body_battery_raw(
    repo: BiometricsRepo,
    date: _OptionalFilterDate = None,
):
    """Get raw body-battery readings."""
    return raw_biometrics_uc.get_body_battery_raw(
        repo, date=date.isoformat() if date is not None else None
    )


@body_battery_router.get("/daily", response_model=BodyBatteryDailyResponse)
def get_body_battery_daily(repo: BiometricsRepo):
    """Return daily Body Battery metrics and period summaries."""
    return daily_aggregates_uc.get_body_battery_daily(repo)


@body_battery_router.get("/analysis", response_model=BodyBatteryAnalysisResponse)
def get_body_battery_analysis(repo: BiometricsRepo):
    """Return period-level body battery analysis (trend, weekly boxplots)."""
    return metric_analysis_uc.load_body_battery_analysis(repo)


@respiration_router.get("/raw", response_model=RespirationRawResponse)
def get_respiration_raw(
    repo: BiometricsRepo,
    date: _OptionalFilterDate = None,
):
    """Get raw respiration readings."""
    return raw_biometrics_uc.get_respiration_raw(
        repo, date=date.isoformat() if date is not None else None
    )


@respiration_router.get("/daily", response_model=RespirationDailyResponse)
def get_respiration_daily(repo: BiometricsRepo):
    """Return daily respiration metrics and period summaries."""
    return daily_aggregates_uc.get_respiration_daily(repo)


@pulse_ox_router.get("/raw", response_model=SpO2RawResponse)
def get_pulse_ox_raw(
    repo: BiometricsRepo,
    date: _OptionalFilterDate = None,
):
    """Get raw pulse-ox readings."""
    return raw_biometrics_uc.get_spo2_raw(
        repo, date=date.isoformat() if date is not None else None
    )


@pulse_ox_router.get("/daily", response_model=SpO2DailyResponse)
def get_pulse_ox_daily(repo: BiometricsRepo):
    """Return daily pulse-ox metrics and period summaries."""
    return daily_aggregates_uc.get_spo2_daily(repo)


@runs_router.get("", response_model=RunsListResponse)
def list_runs_route(
    repo: RunsRepo,
    from_date: _RunsFromDate = None,
    to_date: _RunsToDate = None,
):
    """List tracked runs, newest first."""
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(status_code=422, detail="from must be on or before to")
    return runs_uc.list_runs(
        repo,
        from_date=from_date.isoformat() if from_date is not None else None,
        to_date=to_date.isoformat() if to_date is not None else None,
    )


@runs_router.get("/{run_id}", response_model=RunDetailResponse)
def get_run_route(repo: RunsRepo, run_id: str):
    """Full run detail: session stats, laps, zones, run/walk spans."""
    return runs_uc.get_run(repo, run_id)


@runs_router.get("/{run_id}/series", response_model=RunSeriesResponse)
def get_run_series_route(repo: RunsRepo, run_id: str):
    """Chart-ready column arrays for one run."""
    return runs_uc.get_run_series(repo, run_id)
