"""Compatibility wrapper for Garmin analytics heart-rate analysis."""

from app.bootstrap.container import build_container
from app.domains.garmin_analytics.application.heart_rate_analysis import (
    _compute_circadian_profile,
    _compute_daily_avg_trend,
    _compute_heart_rate_analysis,
    _compute_hr_distribution,
    _compute_resting_hr_trend,
    _compute_sleeping_hr_trend,
    _compute_weekly_boxplots,
)
from app.domains.garmin_analytics.application.heart_rate_analysis import (
    load_heart_rate_analysis as _load_heart_rate_analysis,
)
from app.domains.garmin_analytics.application.heart_rate_analysis import (
    load_hr_distribution as _load_hr_distribution,
)
from app.models import HeartRateAnalysisResponse, HRDistributionResponse


def load_heart_rate_analysis() -> HeartRateAnalysisResponse:
    return _load_heart_rate_analysis(build_container().garmin_biometrics_repo)


def load_hr_distribution(date: str) -> HRDistributionResponse:
    return _load_hr_distribution(build_container().garmin_biometrics_repo, date)


__all__ = [
    "_compute_circadian_profile",
    "_compute_daily_avg_trend",
    "_compute_heart_rate_analysis",
    "_compute_hr_distribution",
    "_compute_resting_hr_trend",
    "_compute_sleeping_hr_trend",
    "_compute_weekly_boxplots",
    "load_heart_rate_analysis",
    "load_hr_distribution",
]
