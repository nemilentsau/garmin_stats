"""Runs endpoint response contracts.

Embeds the canonical `garmin_health` running-activity contracts directly
(mirrors how `raw.py` embeds biometric reading contracts) rather than
re-declaring their fields here.
"""

from app.contracts.base import DefaultsRequired
from app.domains.garmin_health.contracts import (
    RunningActivityLap,
    RunningActivitySeries,
    RunningActivitySession,
)


class RunListItem(DefaultsRequired):
    """One row of the runs list: session summary fields, no laps/series."""

    id: str
    session_date: str
    start_time_local: str
    activity_name: str | None = None
    sub_sport: str | None = None
    distance_m: float | None = None
    timer_time_s: float | None = None
    pace_min_per_km: float | None = None
    avg_heart_rate_bpm: int | None = None
    hr_source: str | None = None
    training_load: float | None = None
    aerobic_training_effect: float | None = None
    has_heart_rate: bool = False
    has_power: bool = False
    has_running_dynamics: bool = False


class RunsListResponse(DefaultsRequired):
    """Runs list endpoint response."""

    runs: list[RunListItem] = []


class RunDetailResponse(DefaultsRequired):
    """Single-run detail endpoint response: full session stats plus laps."""

    session: RunningActivitySession
    laps: list[RunningActivityLap] = []


class RunSeriesResponse(DefaultsRequired):
    """Single-run chart-series endpoint response, with backend-derived pace."""

    series: RunningActivitySeries
    pace_min_per_km: list[float | None] = []
