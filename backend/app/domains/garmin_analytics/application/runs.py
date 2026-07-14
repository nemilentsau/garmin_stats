"""Run read use cases: list, detail, and chart-ready display projections.

Owns the display-ready projection of stored run rows: date-window filtering,
newest-first ordering, unit conversion to the project's imperial display rule
(mi, min/mi, ft, °F — see CLAUDE.md), and the pace array derived from the
speed series (frontend never computes). Storage access goes through
RunsReadRepository; the embedded `session`/`laps` stay metric (canonical
storage units) — every converted field lives in `RunDisplayStats`/
`LapDisplayRow`/the series' imperial arrays.
"""

from typing import Protocol

from app.domains.garmin_analytics.application.dependencies import RunsReadRepository
from app.domains.garmin_analytics.contracts import (
    LapDisplayRow,
    RunDetailResponse,
    RunDisplayStats,
    RunListItem,
    RunSeriesResponse,
    RunsListResponse,
)
from app.domains.garmin_analytics.domain.run_display import (
    active_running_display_mask,
    apply_display_mask,
    detrend_closed_loop_elevation,
    elevation_gain_loss_m,
    smooth_elevation_by_distance,
    zone_display_rows,
)

_MIN_PACE_SPEED_MPS = 0.5

# Imperial conversion constants (CLAUDE.md imperial display rule). Exact, not
# approximated, so repeated conversions stay consistent across call sites.
_M_PER_MI = 1609.344
_KM_TO_MI = 1.609344
_M_TO_FT = 3.28084
_MPS_TO_MPH = 2.2369363


class _ElevationSeriesView(Protocol):
    @property
    def distance_m(self) -> list[float | None]: ...

    @property
    def altitude_m(self) -> list[float | None]: ...


class _ElevationLocationView(Protocol):
    @property
    def start_lat(self) -> float | None: ...

    @property
    def start_lon(self) -> float | None: ...

    @property
    def end_lat(self) -> float | None: ...

    @property
    def end_lon(self) -> float | None: ...


def _m_to_mi(value_m: float | None) -> float | None:
    """Meters -> miles, 2dp. None-preserving."""
    return None if value_m is None else round(value_m / _M_PER_MI, 2)


def _minkm_to_minmi(value_min_per_km: float | None) -> float | None:
    """min/km -> min/mi, 2dp. None-preserving."""
    return None if value_min_per_km is None else round(value_min_per_km * _KM_TO_MI, 2)


def _m_to_ft(value_m: float | None) -> float | None:
    """Meters -> feet, rounded to the nearest whole foot. None-preserving."""
    return None if value_m is None else round(value_m * _M_TO_FT, 0)


def _c_to_f(value_c: float | None) -> float | None:
    """Celsius -> Fahrenheit, 1dp. None-preserving."""
    return None if value_c is None else round(value_c * 9 / 5 + 32, 1)


def _mps_to_mph(value_mps: float | None) -> float | None:
    """m/s -> mph, 1dp. None-preserving."""
    return None if value_mps is None else round(value_mps * _MPS_TO_MPH, 1)


def _mm_to_cm(value_mm: float | None) -> float | None:
    """Millimeters -> centimeters, 1dp. None-preserving.

    Vertical oscillation displays in cm (Garmin convention) while stride
    length stays in meters and GCT stays in ms — see CLAUDE.md.
    """
    return None if value_mm is None else round(value_mm / 10, 1)


def _mm_to_m(value_mm: float | None) -> float | None:
    """Millimeters -> meters, 3dp. None-preserving."""
    return None if value_mm is None else round(value_mm / 1000, 3)


def _ground_contact_balance_label(value_pct: float | None) -> str | None:
    """Render Garmin's "L / R" stance-time balance split, e.g. "49.8% L / 50.2% R".

    The stored value is the left foot's share of total ground contact time;
    the right share is its complement (100 - value). Both sides round to 1dp
    independently, matching Connect's display — this is arithmetic on one
    stored field, so it belongs backend-side per the frontend display-only
    rule (CLAUDE.md). None-preserving (wrist-only runs have no balance data).
    """
    if value_pct is None:
        return None
    return f"{round(value_pct, 1):.1f}% L / {round(100 - value_pct, 1):.1f}% R"


def _speed_mps_to_pace_min_per_km(value_mps: float | None) -> float | None:
    """m/s -> min/km pace; None below `_MIN_PACE_SPEED_MPS` or when speed is None.

    Deliberately unrounded: callers multiply by `_KM_TO_MI` before rounding so
    a mile-pace value never loses precision to an intermediate km-pace round.
    """
    if value_mps is None or value_mps < _MIN_PACE_SPEED_MPS:
        return None
    return 1000 / (value_mps * 60)


def _display_elevation_profile(
    series: _ElevationSeriesView | None,
    session: _ElevationLocationView | None,
) -> list[float | None] | None:
    """Build the display profile while leaving stored altitude untouched."""
    if series is None:
        return None
    smoothed = smooth_elevation_by_distance(series.distance_m, series.altitude_m)
    if smoothed is None:
        return None
    if sum(value is not None for value in smoothed) < 2:
        return None

    start_lat = session.start_lat if session is not None else None
    start_lon = session.start_lon if session is not None else None
    end_lat = session.end_lat if session is not None else None
    end_lon = session.end_lon if session is not None else None
    return detrend_closed_loop_elevation(
        series.distance_m,
        smoothed,
        start_lat=start_lat,
        start_lon=start_lon,
        end_lat=end_lat,
        end_lon=end_lon,
    )


def list_runs(
    repo: RunsReadRepository, from_date: str | None = None, to_date: str | None = None
) -> RunsListResponse:
    """Runs newest-first, optionally windowed by session_date (inclusive)."""
    sessions = repo.load_sessions()
    if from_date:
        sessions = [s for s in sessions if s.session_date >= from_date]
    if to_date:
        sessions = [s for s in sessions if s.session_date <= to_date]
    sessions.sort(key=lambda s: (s.session_date, s.start_time_local), reverse=True)
    return RunsListResponse(
        runs=[
            RunListItem(
                id=s.id,
                session_date=s.session_date,
                start_time_local=s.start_time_local,
                activity_name=s.activity_name,
                sub_sport=s.sub_sport,
                distance_mi=_m_to_mi(s.distance_m),
                timer_time_s=s.timer_time_s,
                pace_min_per_mi=_minkm_to_minmi(s.pace_min_per_km),
                avg_heart_rate_bpm=s.avg_heart_rate_bpm,
                hr_source=s.hr_source,
                training_load=s.training_load,
                aerobic_training_effect=s.aerobic_training_effect,
                has_heart_rate=s.has_heart_rate,
                has_power=s.has_power,
                has_running_dynamics=s.has_running_dynamics,
            )
            for s in sessions
        ]
    )


def get_run(repo: RunsReadRepository, run_id: str) -> RunDetailResponse:
    """Full run detail (metric session + laps) plus the imperial `display` projection.

    Raises LookupError if run_id is unknown. GAP (`gap_min_per_mi`) derives from
    `grade_adjusted_avg_speed_mps` via the same speed->pace formula as the chart
    series, so it shares that formula's None/threshold behavior.
    """
    session = repo.load_session(run_id)
    if session is None:
        raise LookupError(f"Run {run_id} not found")
    laps = repo.load_laps(run_id)
    elevation_profile = _display_elevation_profile(repo.load_series(run_id), session)
    elevation_totals = (
        elevation_gain_loss_m(elevation_profile)
        if elevation_profile is not None
        else None
    )
    display = RunDisplayStats(
        distance_mi=_m_to_mi(session.distance_m),
        pace_min_per_mi=_minkm_to_minmi(session.pace_min_per_km),
        gap_min_per_mi=_minkm_to_minmi(
            _speed_mps_to_pace_min_per_km(session.grade_adjusted_avg_speed_mps)
        ),
        avg_speed_mph=_mps_to_mph(session.avg_speed_mps),
        max_speed_mph=_mps_to_mph(session.max_speed_mps),
        total_ascent_ft=_m_to_ft(
            elevation_totals[0] if elevation_totals is not None else session.total_ascent_m
        ),
        total_descent_ft=_m_to_ft(
            elevation_totals[1] if elevation_totals is not None else session.total_descent_m
        ),
        avg_temperature_f=_c_to_f(session.avg_temperature_c),
        min_temperature_f=_c_to_f(session.min_temperature_c),
        max_temperature_f=_c_to_f(session.max_temperature_c),
        avg_vertical_oscillation_cm=_mm_to_cm(session.avg_vertical_oscillation_mm),
        avg_ground_contact_balance_label=_ground_contact_balance_label(
            session.avg_ground_contact_balance_pct
        ),
        avg_stance_time_pct=session.avg_stance_time_pct,
        avg_respiration_rate_brpm=session.avg_respiration_rate_brpm,
        max_respiration_rate_brpm=session.max_respiration_rate_brpm,
        min_respiration_rate_brpm=session.min_respiration_rate_brpm,
        stamina_beginning_potential_pct=session.stamina_beginning_potential_pct,
        stamina_ending_potential_pct=session.stamina_ending_potential_pct,
        stamina_min_pct=session.stamina_min_pct,
        heart_rate_zones=(
            zone_display_rows(
                session.time_in_zones.time_in_hr_zone_s,
                session.time_in_zones.hr_zone_high_boundary_bpm,
                unit="bpm",
            )
            if session.time_in_zones is not None
            else []
        ),
        power_zones=(
            zone_display_rows(
                session.time_in_zones.time_in_power_zone_s,
                session.time_in_zones.power_zone_high_boundary_w,
                unit="W",
            )
            if session.time_in_zones is not None
            else []
        ),
        lap_display=[
            LapDisplayRow(
                lap_index=lap.lap_index,
                distance_mi=_m_to_mi(lap.distance_m),
                pace_min_per_mi=_minkm_to_minmi(lap.pace_min_per_km),
                avg_ground_contact_balance_label=_ground_contact_balance_label(
                    lap.avg_ground_contact_balance_pct
                ),
                avg_respiration_rate_brpm=lap.avg_respiration_rate_brpm,
                avg_vertical_oscillation_cm=_mm_to_cm(lap.avg_vertical_oscillation_mm),
            )
            for lap in laps
        ],
    )
    return RunDetailResponse(session=session, laps=laps, display=display)


def _series_pace_min_per_mi(speed_mps: list[float | None]) -> list[float | None]:
    """Per-sample m/s -> min/mi pace, 3dp (finer than the 2dp scalar display fields).

    Derives min/km the same way as before (see `_speed_mps_to_pace_min_per_km`),
    then converts to min/mi in the same expression so the mile value is never
    rounded twice.
    """
    paces: list[float | None] = []
    for v in speed_mps:
        pace_min_per_km = _speed_mps_to_pace_min_per_km(v)
        paces.append(None if pace_min_per_km is None else round(pace_min_per_km * _KM_TO_MI, 3))
    return paces


def get_run_series(repo: RunsReadRepository, run_id: str) -> RunSeriesResponse:
    """Chart-ready record series (metric) plus imperial arrays; raises LookupError if unknown.

    Pace is null below `_MIN_PACE_SPEED_MPS` (near-zero/stopped GPS speed would
    otherwise blow up to a meaningless pace) and for missing speed samples.
    """
    series = repo.load_series(run_id)
    if series is None:
        raise LookupError(f"Run {run_id} not found")
    session = repo.load_session(run_id)
    display_mask = active_running_display_mask(series.elapsed_s, series.run_walk_spans)
    elevation_profile = _display_elevation_profile(series, session)
    return RunSeriesResponse(
        series=series,
        pace_min_per_mi=apply_display_mask(
            _series_pace_min_per_mi(series.speed_mps), display_mask
        ),
        altitude_ft=(
            [_m_to_ft(value) for value in elevation_profile]
            if elevation_profile is not None
            else [_m_to_ft(value) for value in series.altitude_m]
        ),
        temperature_f=[_c_to_f(v) for v in series.temperature_c],
        distance_mi=[_m_to_mi(v) for v in series.distance_m],
        cadence_spm=apply_display_mask(series.cadence_spm, display_mask),
        step_length_m=apply_display_mask(
            [_mm_to_m(value) for value in series.step_length_mm], display_mask
        ),
        vertical_oscillation_cm=apply_display_mask(
            [_mm_to_cm(value) for value in series.vertical_oscillation_mm], display_mask
        ),
        vertical_ratio_pct=apply_display_mask(series.vertical_ratio_pct, display_mask),
        ground_contact_time_ms=apply_display_mask(series.stance_time_ms, display_mask),
        ground_contact_balance_pct=apply_display_mask(
            series.stance_time_balance_pct, display_mask
        ),
        stance_time_pct=apply_display_mask(series.stance_time_pct, display_mask),
    )
