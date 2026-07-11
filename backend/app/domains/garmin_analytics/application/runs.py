"""Run read use cases: list, detail, and chart series with derived pace.

Owns the display-ready projection of stored run rows: date-window filtering,
newest-first ordering, and the pace array derived from the speed series
(frontend never computes). Storage access goes through RunsReadRepository.
"""

from app.domains.garmin_analytics.application.dependencies import RunsReadRepository
from app.domains.garmin_analytics.contracts import (
    RunDetailResponse,
    RunListItem,
    RunSeriesResponse,
    RunsListResponse,
)

_MIN_PACE_SPEED_MPS = 0.5


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
                distance_m=s.distance_m,
                timer_time_s=s.timer_time_s,
                pace_min_per_km=s.pace_min_per_km,
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
    """Full run detail (session + laps); raises LookupError if run_id is unknown."""
    session = repo.load_session(run_id)
    if session is None:
        raise LookupError(f"Run {run_id} not found")
    return RunDetailResponse(session=session, laps=repo.load_laps(run_id))


def get_run_series(repo: RunsReadRepository, run_id: str) -> RunSeriesResponse:
    """Chart-ready record series with derived pace; raises LookupError if unknown.

    Pace is null below `_MIN_PACE_SPEED_MPS` (near-zero/stopped GPS speed would
    otherwise blow up to a meaningless pace) and for missing speed samples.
    """
    series = repo.load_series(run_id)
    if series is None:
        raise LookupError(f"Run {run_id} not found")
    pace = [
        round(1000 / (v * 60), 3) if v is not None and v >= _MIN_PACE_SPEED_MPS else None
        for v in series.speed_mps
    ]
    return RunSeriesResponse(series=series, pace_min_per_km=pace)
