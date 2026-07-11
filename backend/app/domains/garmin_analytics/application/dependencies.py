"""Application-facing dependency protocols for Garmin analytics.

Use cases depend on these protocols instead of SQLite details so tests can pass
plain in-memory repositories and the domain layer stays persistence-free.
"""

from typing import Protocol

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


class BiometricReadRepository(Protocol):
    """Read access for current Garmin biometric marts."""

    def load_daily_metrics(self, *, last_n: int | None = None) -> list[DailyMetric]: ...

    def load_wellness(self, date: str | None = None) -> list[DayWellness]: ...

    def load_sleep(self, date: str | None = None) -> list[DaySleep]: ...

    def load_hrv(self, date: str | None = None) -> list[DayHrv]: ...

    def load_skin_temp(self, date: str | None = None) -> list[DaySkinTemp]: ...


class RunsReadRepository(Protocol):
    """Read access for the running-activity mart (sessions, laps, record series)."""

    def load_sessions(self) -> list[RunningActivitySession]: ...

    def load_session(self, run_id: str) -> RunningActivitySession | None: ...

    def load_laps(self, run_id: str) -> list[RunningActivityLap]: ...

    def load_series(self, run_id: str) -> RunningActivitySeries | None: ...
