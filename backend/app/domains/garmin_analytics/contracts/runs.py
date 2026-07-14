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
    render straight from the embedded `RunningActivityLap`. The strap-only
    fields below are None on wrist-only laps, same as their session-level
    counterparts on `RunDisplayStats`.
    """

    lap_index: int
    distance_mi: float | None = None
    pace_min_per_mi: float | None = None
    avg_ground_contact_balance_label: str | None = None
    avg_respiration_rate_brpm: float | None = None
    avg_vertical_oscillation_cm: float | None = None


class RunDisplayStats(DefaultsRequired):
    """Imperial display projection of a run's canonical (metric) session stats.

    Every field is None-preserving from its metric source; see the `_*_to_*`
    conversion helpers in `application/runs.py` for the exact constants and
    rounding rule each field uses. `avg_ground_contact_balance_label` and the
    respiration fields are strap-only: they render as None when the run has
    no chest-strap running dynamics (wrist-only runs). The `stamina_*` fields
    are watch-level (Firstbeat), not strap-dependent — pass-through, already
    dimensionless ints, no conversion.
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
    avg_ground_contact_balance_label: str | None = None
    avg_stance_time_pct: float | None = None
    avg_respiration_rate_brpm: float | None = None
    max_respiration_rate_brpm: float | None = None
    min_respiration_rate_brpm: float | None = None
    stamina_beginning_potential_pct: int | None = None
    stamina_ending_potential_pct: int | None = None
    stamina_min_pct: int | None = None
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
    """Canonical run series plus index-aligned, display-ready chart arrays.

    `series` is the untouched metric FIT projection. Top-level movement arrays
    are chart projections: start/resume sensor-settling samples and explicit
    non-running spans become positional nulls without deleting source records.
    `altitude_ft` is the smoothed display profile. `step_length_m` and
    `vertical_oscillation_cm` retain Garmin's metric display exceptions.

    Respiration, stamina, and performance-condition arrays remain only inside
    `series`: they are not movement-dependent charts and need no display copy.
    """

    series: RunningActivitySeries
    pace_min_per_mi: list[float | None] = []
    altitude_ft: list[float | None] = []
    temperature_f: list[float | None] = []
    distance_mi: list[float | None] = []
    cadence_spm: list[float | None] = []
    step_length_m: list[float | None] = []
    vertical_oscillation_cm: list[float | None] = []
    vertical_ratio_pct: list[float | None] = []
    ground_contact_time_ms: list[float | None] = []
    ground_contact_balance_pct: list[float | None] = []
    stance_time_pct: list[float | None] = []
