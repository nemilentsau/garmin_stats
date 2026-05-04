"""Compatibility wrapper for Garmin analytics HRV analysis."""

from app.bootstrap.container import build_container
from app.domains.garmin_analytics.application.hrv_analysis import (
    _compute_hrv_analysis,
    _compute_nightly_hrv_trend,
    _compute_pattern_window,
    _compute_pattern_windows,
    _compute_weekly_hrv_boxplots,
)
from app.domains.garmin_analytics.application.hrv_analysis import (
    load_hrv_analysis as _load_hrv_analysis,
)
from app.models import HrvAnalysisResponse


def load_hrv_analysis() -> HrvAnalysisResponse:
    return _load_hrv_analysis(build_container().garmin_biometrics_repo)


__all__ = [
    "_compute_hrv_analysis",
    "_compute_nightly_hrv_trend",
    "_compute_pattern_window",
    "_compute_pattern_windows",
    "_compute_weekly_hrv_boxplots",
    "load_hrv_analysis",
]
