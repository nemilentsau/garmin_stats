"""Compatibility wrapper for Garmin analytics stress analysis."""

from app.bootstrap.container import build_container
from app.domains.garmin_analytics.application.stress_analysis import (
    _compute_stress_analysis,
    _compute_stress_trend,
    _compute_weekly_stress_boxplots,
)
from app.domains.garmin_analytics.application.stress_analysis import (
    load_stress_analysis as _load_stress_analysis,
)
from app.models import StressAnalysisResponse


def load_stress_analysis() -> StressAnalysisResponse:
    return _load_stress_analysis(build_container().garmin_biometrics_repo)


__all__ = [
    "_compute_stress_analysis",
    "_compute_stress_trend",
    "_compute_weekly_stress_boxplots",
    "load_stress_analysis",
]
