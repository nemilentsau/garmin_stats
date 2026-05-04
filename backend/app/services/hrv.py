"""Compatibility wrapper for Garmin analytics HRV insights."""

from app.bootstrap.container import build_container
from app.domains.garmin_analytics.application.hrv import (
    _compute_day_of_week,
    _compute_hrv_distribution,
    _normalize_hrv_status,
)
from app.domains.garmin_analytics.application.hrv import (
    load_hrv_insights as _load_hrv_insights,
)
from app.models import HrvInsightsResponse


def load_hrv_insights(date: str | None = None) -> HrvInsightsResponse:
    return _load_hrv_insights(
        build_container().garmin_biometrics_repo,
        date,
    )


__all__ = [
    "_compute_day_of_week",
    "_compute_hrv_distribution",
    "_normalize_hrv_status",
    "load_hrv_insights",
]
