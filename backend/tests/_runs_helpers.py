"""Insert helpers for running-activity tables in route tests."""

from datetime import UTC, datetime

from app.domains.garmin_health.contracts import (
    RunningActivityLap,
    RunningActivitySeries,
    RunningActivitySession,
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
) -> None:
    """Insert one running-activity session (+ optional laps + fixed series).

    The metric-override kwargs (ascent/descent/temperature/speed/vertical
    oscillation) default to `None` so existing callers are unaffected; pass
    them to exercise the imperial-display conversion helpers' non-None
    branches in `application/runs.py` (e.g. `total_ascent_m=139` pins
    `display.total_ascent_ft`).
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
    )
    series = RunningActivitySeries(
        elapsed_s=[0, 1, 2],
        speed_mps=[3.2, 3.3, 0.1],
        heart_rate_bpm=[140, 141, 142],
    )
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
            lap = RunningActivityLap(lap_index=i, distance_m=1609.34)
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
