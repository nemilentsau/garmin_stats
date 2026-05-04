"""Compatibility wrapper for Garmin analytics sleep analysis."""

from app.bootstrap.container import build_container
from app.domains.garmin_analytics.application.sleep_analysis import (
    _compute_sleep_analysis,
    _compute_sleep_trend,
    _compute_weekly_sleep_boxplots,
)
from app.domains.garmin_analytics.application.sleep_analysis import (
    load_sleep_analysis as _load_sleep_analysis,
)
from app.models import SleepAnalysisResponse


def load_sleep_analysis() -> SleepAnalysisResponse:
    return _load_sleep_analysis(build_container().garmin_biometrics_repo)


__all__ = [
    "_compute_sleep_analysis",
    "_compute_sleep_trend",
    "_compute_weekly_sleep_boxplots",
    "load_sleep_analysis",
]
