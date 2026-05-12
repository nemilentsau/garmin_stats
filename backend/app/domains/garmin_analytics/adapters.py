"""SQLite-backed Garmin biometric read repository.

This module is the single read implementation for ingested Garmin biometric
tables. `SqliteBiometricRepository` satisfies application ports, while the
module-level loaders expose the same reads for legacy callers that have not yet
accepted the repository port.
"""

from pydantic import BaseModel

from app.domains.garmin_health.contracts import (
    DailyMetric,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
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
