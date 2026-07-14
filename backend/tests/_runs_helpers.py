"""Insert helpers for running-activity tables in route tests."""

from datetime import UTC, datetime

from app.domains.garmin_health.contracts import (
    RunningActivityLap,
    RunningActivitySeries,
    RunningActivitySession,
    RunningTimeInZones,
)
from app.infra.sqlite import connect


def insert_run(
    session_date: str,
    run_id: str,
    lap_count: int = 0,
    total_ascent_m: int | None = None,
    total_descent_m: int | None = None,
    avg_temperature_c: float | None = None,
    min_temperature_c: float | None = None,
    max_temperature_c: float | None = None,
    avg_speed_mps: float | None = None,
    max_speed_mps: float | None = None,
    grade_adjusted_avg_speed_mps: float | None = None,
    avg_vertical_oscillation_mm: float | None = None,
    avg_ground_contact_balance_pct: float | None = None,
    avg_stance_time_pct: float | None = None,
    avg_respiration_rate_brpm: float | None = None,
    max_respiration_rate_brpm: float | None = None,
    min_respiration_rate_brpm: float | None = None,
    stance_time_balance_pct: list[float | None] | None = None,
    respiration_rate_brpm: list[float | None] | None = None,
    stance_time_pct: list[float | None] | None = None,
    stamina_beginning_potential_pct: int | None = None,
    stamina_ending_potential_pct: int | None = None,
    stamina_min_pct: int | None = None,
    stamina_pct: list[int | None] | None = None,
    stamina_potential_pct: list[int | None] | None = None,
    performance_condition: list[int | None] | None = None,
    lap_avg_ground_contact_balance_pct: float | None = None,
    lap_avg_respiration_rate_brpm: float | None = None,
    lap_avg_vertical_oscillation_mm: float | None = None,
    time_in_zones: RunningTimeInZones | None = None,
) -> None:
    """Insert one running-activity session (+ optional laps + fixed series).

    The metric-override kwargs (ascent/descent/temperature/speed/vertical
    oscillation/strap dynamics) default to `None` so existing callers are
    unaffected; pass them to exercise the imperial-display conversion
    helpers' non-None branches in `application/runs.py` (e.g.
    `total_ascent_m=139` pins `display.total_ascent_ft`).

    The `stance_time_balance_pct`/`respiration_rate_brpm`/`stance_time_pct`
    series kwargs override the fixed 3-sample series fixture (default `None`
    leaves those arrays at the model's `[]` default, matching a wrist-only
    run's absent strap dynamics). `lap_avg_*` kwargs apply the same lap-level
    strap-dynamics value to every generated lap.

    `stamina_pct`/`stamina_potential_pct`/`performance_condition` series kwargs
    behave the same way (default `None` leaves those arrays empty).
    `stamina_beginning_potential_pct`/`stamina_ending_potential_pct`/
    `stamina_min_pct` set the session-level derived scalars directly — the real
    parser derives these from the series at parse time, but this helper writes
    pre-derived values straight onto the stored session row (route tests exercise
    the API pass-through, not the parser's derivation, which is covered in
    `test_activity_parser.py`).
    """
    session = RunningActivitySession(
        id=run_id,
        source_file=f"{session_date}/105726_running_generic.fit",
        session_date=session_date,
        start_time_local=f"{session_date}T10:57:26",
        distance_m=9695.29,
        timer_time_s=3050.674,
        pace_min_per_km=5.24,
        avg_heart_rate_bpm=139,
        hr_source="strap",
        has_heart_rate=True,
        total_ascent_m=total_ascent_m,
        total_descent_m=total_descent_m,
        avg_temperature_c=avg_temperature_c,
        min_temperature_c=min_temperature_c,
        max_temperature_c=max_temperature_c,
        avg_speed_mps=avg_speed_mps,
        max_speed_mps=max_speed_mps,
        grade_adjusted_avg_speed_mps=grade_adjusted_avg_speed_mps,
        avg_vertical_oscillation_mm=avg_vertical_oscillation_mm,
        avg_ground_contact_balance_pct=avg_ground_contact_balance_pct,
        avg_stance_time_pct=avg_stance_time_pct,
        avg_respiration_rate_brpm=avg_respiration_rate_brpm,
        max_respiration_rate_brpm=max_respiration_rate_brpm,
        min_respiration_rate_brpm=min_respiration_rate_brpm,
        stamina_beginning_potential_pct=stamina_beginning_potential_pct,
        stamina_ending_potential_pct=stamina_ending_potential_pct,
        stamina_min_pct=stamina_min_pct,
        time_in_zones=time_in_zones,
    )
    series_kwargs = {
        "elapsed_s": [0, 1, 2],
        "speed_mps": [3.2, 3.3, 0.1],
        "heart_rate_bpm": [140, 141, 142],
    }
    if stance_time_balance_pct is not None:
        series_kwargs["stance_time_balance_pct"] = stance_time_balance_pct
    if respiration_rate_brpm is not None:
        series_kwargs["respiration_rate_brpm"] = respiration_rate_brpm
    if stance_time_pct is not None:
        series_kwargs["stance_time_pct"] = stance_time_pct
    if stamina_pct is not None:
        series_kwargs["stamina_pct"] = stamina_pct
    if stamina_potential_pct is not None:
        series_kwargs["stamina_potential_pct"] = stamina_potential_pct
    if performance_condition is not None:
        series_kwargs["performance_condition"] = performance_condition
    series = RunningActivitySeries(**series_kwargs)
    now = datetime.now(UTC).isoformat()
    with connect() as con:
        con.execute(
            "INSERT OR REPLACE INTO running_activity_sessions "
            "(id, activity_id, session_date, start_time_local, sub_sport, source_file,"
            " data, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, run_id, session_date, session.start_time_local, "generic",
             session.source_file, session.model_dump_json(), now, now),
        )
        for i in range(lap_count):
            lap = RunningActivityLap(
                lap_index=i,
                distance_m=1609.34,
                avg_ground_contact_balance_pct=lap_avg_ground_contact_balance_pct,
                avg_respiration_rate_brpm=lap_avg_respiration_rate_brpm,
                avg_vertical_oscillation_mm=lap_avg_vertical_oscillation_mm,
            )
            con.execute(
                "INSERT OR REPLACE INTO running_activity_laps (session_id, lap_index, data)"
                " VALUES (?, ?, ?)",
                (run_id, i, lap.model_dump_json()),
            )
        con.execute(
            "INSERT OR REPLACE INTO running_activity_series (session_id, data) VALUES (?, ?)",
            (run_id, series.model_dump_json()),
        )
        con.commit()
