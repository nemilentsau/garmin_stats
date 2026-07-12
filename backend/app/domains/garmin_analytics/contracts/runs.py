"""Runs endpoint response contracts.

Embeds the canonical `garmin_health` running-activity contracts directly
(mirrors how `raw.py` embeds biometric reading contracts) rather than
re-declaring their fields here.

Per the project-wide imperial display rule, every user-facing field on these
response models is US imperial (miles, min/mi, ft, °F); the embedded session
and laps stay metric (canonical storage units) and are converted at read time
by `application/runs.py`. Frontend does no unit math — see `RunDisplayStats`.
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
    distance_mi: float | None = None
    timer_time_s: float | None = None
    pace_min_per_mi: float | None = None
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


class LapDisplayRow(DefaultsRequired):
    """One lap's imperial display fields, joined to the embedded lap by `lap_index`.

    The lap's other fields (time, HR, cadence, ...) need no unit conversion and
    render straight from the embedded `RunningActivityLap`.
    """

    lap_index: int
    distance_mi: float | None = None
    pace_min_per_mi: float | None = None


class RunDisplayStats(DefaultsRequired):
    """Imperial display projection of a run's canonical (metric) session stats.

    Every field is None-preserving from its metric source; see the `_*_to_*`
    conversion helpers in `application/runs.py` for the exact constants and
    rounding rule each field uses.
    """

    distance_mi: float | None = None
    pace_min_per_mi: float | None = None
    gap_min_per_mi: float | None = None
    avg_speed_mph: float | None = None
    max_speed_mph: float | None = None
    total_ascent_ft: float | None = None
    total_descent_ft: float | None = None
    avg_temperature_f: float | None = None
    min_temperature_f: float | None = None
    max_temperature_f: float | None = None
    avg_vertical_oscillation_cm: float | None = None
    lap_display: list[LapDisplayRow] = []


class RunDetailResponse(DefaultsRequired):
    """Single-run detail endpoint response: full session stats plus laps.

    `session`/`laps` stay metric (canonical); `display` is the imperial
    projection the frontend renders from.
    """

    session: RunningActivitySession
    laps: list[RunningActivityLap] = []
    display: RunDisplayStats


class RunSeriesResponse(DefaultsRequired):
    """Single-run chart-series endpoint response: metric series plus imperial arrays.

    `series` stays metric (canonical); `pace_min_per_mi`/`altitude_ft`/
    `temperature_f`/`distance_mi` are the backend-derived imperial arrays the
    frontend charts bind to, index-aligned with `series.elapsed_s`.
    """

    series: RunningActivitySeries
    pace_min_per_mi: list[float | None] = []
    altitude_ft: list[float | None] = []
    temperature_f: list[float | None] = []
    distance_mi: list[float | None] = []
