"""SQLite-backed Garmin biometric and running-activity read repositories.

This module is the single read implementation for ingested Garmin biometric
tables. `SqliteBiometricRepository` satisfies application ports, while the
module-level loaders expose the same reads for legacy callers that have not yet
accepted the repository port. `SqliteRunsRepository` reads the running-activity
mart written by `garmin_sync` (sessions, laps, per-second record series).
"""

from pydantic import BaseModel

from app.domains.garmin_health.contracts import (
    DailyMetric,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
    RunningActivityLap,
    RunningActivitySeries,
    RunningActivitySession,
)
from app.infra import cache
from app.infra.sqlite import connect


def load_daily_metrics(*, last_n: int | None = None) -> list[DailyMetric]:
    """Load persisted daily metrics ordered by date, optionally limited to the tail."""
    if last_n is None:
        return cache.cached(cache.DAILY_METRICS, _fetch_daily_metrics)
    if last_n <= 0:
        return []

    cached_metrics = cache.get(cache.DAILY_METRICS)
    if cached_metrics is not None:
        return cached_metrics[-last_n:]
    return _fetch_recent_daily_metrics(last_n)


def _fetch_daily_metrics() -> list[DailyMetric]:
    with connect() as con:
        rows = con.execute("SELECT data FROM daily_metrics ORDER BY date").fetchall()
    return [DailyMetric.model_validate_json(row["data"]) for row in rows]


def _fetch_recent_daily_metrics(last_n: int) -> list[DailyMetric]:
    with connect() as con:
        rows = con.execute(
            "SELECT data FROM daily_metrics ORDER BY date DESC LIMIT ?",
            (last_n,),
        ).fetchall()
    return [DailyMetric.model_validate_json(row["data"]) for row in reversed(rows)]


def _load_day_table[M: BaseModel](
    table: str,
    model: type[M],
    cache_key: str,
    date: str | None = None,
) -> list[M]:
    """Load one JSON-backed day table with shared all-days caching semantics."""
    if date is not None:
        all_cached = cache.get(cache_key)
        if all_cached is not None:
            return [item for item in all_cached if item.date == date]
        with connect() as con:
            rows = con.execute(
                f"SELECT data FROM {table} WHERE date = ?",  # noqa: S608
                (date,),
            ).fetchall()
        return [model.model_validate_json(row["data"]) for row in rows]

    hit = cache.get(cache_key)
    if hit is not None:
        return hit
    generation = cache.generation()
    with connect() as con:
        rows = con.execute(
            f"SELECT data FROM {table} ORDER BY date"  # noqa: S608
        ).fetchall()
    result = [model.model_validate_json(row["data"]) for row in rows]
    cache.put(cache_key, result, generation)
    return result


class SqliteBiometricRepository:
    """Repository adapter used by Garmin analytics application use cases."""

    def load_daily_metrics(self, *, last_n: int | None = None) -> list[DailyMetric]:
        return load_daily_metrics(last_n=last_n)

    def load_wellness(self, date: str | None = None) -> list[DayWellness]:
        return load_wellness(date)

    def load_sleep(self, date: str | None = None) -> list[DaySleep]:
        return load_sleep(date)

    def load_hrv(self, date: str | None = None) -> list[DayHrv]:
        return load_hrv(date)

    def load_skin_temp(self, date: str | None = None) -> list[DaySkinTemp]:
        return load_skin_temp(date)


def load_wellness(date: str | None = None) -> list[DayWellness]:
    """Load parsed wellness rows, optionally restricted to one local date."""
    return _load_day_table("wellness_data", DayWellness, cache.WELLNESS_ALL, date)


def load_sleep(date: str | None = None) -> list[DaySleep]:
    """Load parsed sleep rows, optionally restricted to one local date."""
    return _load_day_table("sleep_data", DaySleep, cache.SLEEP_ALL, date)


def load_hrv(date: str | None = None) -> list[DayHrv]:
    """Load parsed HRV rows, optionally restricted to one local date."""
    return _load_day_table("hrv_data", DayHrv, cache.HRV_ALL, date)


def load_skin_temp(date: str | None = None) -> list[DaySkinTemp]:
    """Load parsed skin-temperature rows, optionally restricted to one local date."""
    return _load_day_table("skin_temp_data", DaySkinTemp, cache.SKIN_TEMP_ALL, date)


class SqliteRunsRepository:
    """Repository adapter for the running-activity mart used by runs use cases."""

    def load_sessions(self) -> list[RunningActivitySession]:
        return load_run_sessions()

    def load_session(self, run_id: str) -> RunningActivitySession | None:
        return load_run_session(run_id)

    def load_laps(self, run_id: str) -> list[RunningActivityLap]:
        return load_run_laps(run_id)

    def load_series(self, run_id: str) -> RunningActivitySeries | None:
        return load_run_series(run_id)


def load_run_sessions() -> list[RunningActivitySession]:
    """Load all run sessions ordered by date/start time, cached across requests."""
    return cache.cached(cache.RUNS_SESSIONS, _fetch_run_sessions)


def _fetch_run_sessions() -> list[RunningActivitySession]:
    with connect() as con:
        rows = con.execute(
            "SELECT data FROM running_activity_sessions ORDER BY session_date, start_time_local"
        ).fetchall()
    return [RunningActivitySession.model_validate_json(row["data"]) for row in rows]


def load_run_session(run_id: str) -> RunningActivitySession | None:
    """Load one run session by id, or None if it doesn't exist.

    Uncached (unlike `load_run_sessions`): detail reads are per-page and keyed,
    not an all-rows scan worth caching.
    """
    with connect() as con:
        row = con.execute(
            "SELECT data FROM running_activity_sessions WHERE id = ?",
            (run_id,),
        ).fetchone()
    return RunningActivitySession.model_validate_json(row["data"]) if row else None


def load_run_laps(run_id: str) -> list[RunningActivityLap]:
    """Load laps for one run session ordered by lap_index. Uncached (see load_run_session)."""
    with connect() as con:
        rows = con.execute(
            "SELECT data FROM running_activity_laps WHERE session_id = ? ORDER BY lap_index",
            (run_id,),
        ).fetchall()
    return [RunningActivityLap.model_validate_json(row["data"]) for row in rows]


def load_run_series(run_id: str) -> RunningActivitySeries | None:
    """Load the record series for one run session, or None if it doesn't exist.

    Uncached: series blobs are large per-second arrays and reads are per-page,
    so caching the full table would waste memory for no repeat-read benefit.
    """
    with connect() as con:
        row = con.execute(
            "SELECT data FROM running_activity_series WHERE session_id = ?",
            (run_id,),
        ).fetchone()
    return RunningActivitySeries.model_validate_json(row["data"]) if row else None
