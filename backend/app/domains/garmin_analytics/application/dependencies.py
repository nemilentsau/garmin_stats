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
)


class BiometricReadRepository(Protocol):
    """Read access for current Garmin biometric marts."""

    def load_daily_metrics(self) -> list[DailyMetric]: ...

    def load_wellness(self, date: str | None = None) -> list[DayWellness]: ...

    def load_sleep(self, date: str | None = None) -> list[DaySleep]: ...

    def load_hrv(self, date: str | None = None) -> list[DayHrv]: ...

    def load_skin_temp(self, date: str | None = None) -> list[DaySkinTemp]: ...
