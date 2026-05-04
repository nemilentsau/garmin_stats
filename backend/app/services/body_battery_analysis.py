"""Compatibility wrapper for Garmin analytics body battery analysis."""

from app.bootstrap.container import build_container
from app.domains.garmin_analytics.application.body_battery_analysis import (
    _compute_body_battery_analysis,
    _compute_body_battery_trend,
    _compute_weekly_body_battery_boxplots,
)
from app.domains.garmin_analytics.application.body_battery_analysis import (
    load_body_battery_analysis as _load_body_battery_analysis,
)
from app.models import BodyBatteryAnalysisResponse


def load_body_battery_analysis() -> BodyBatteryAnalysisResponse:
    return _load_body_battery_analysis(build_container().garmin_biometrics_repo)


__all__ = [
    "_compute_body_battery_analysis",
    "_compute_body_battery_trend",
    "_compute_weekly_body_battery_boxplots",
    "load_body_battery_analysis",
]
