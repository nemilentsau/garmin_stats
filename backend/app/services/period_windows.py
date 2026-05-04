"""Compatibility wrapper for Garmin analytics period summaries."""

from app.bootstrap.container import build_container
from app.domains.garmin_analytics.application.period_summary import (
    load_windowed_period_summary as _load_windowed_period_summary,
)
from app.models import PeriodSummary


def load_windowed_period_summary() -> dict[str, PeriodSummary]:
    """Load pre-computed period summaries for each time window."""
    return _load_windowed_period_summary(build_container().garmin_biometrics_repo)
