"""Application ports for Garmin analytics read models."""

from typing import Protocol

from app.models import DailyMetric, DayHrv, DaySkinTemp, DaySleep, DayWellness


class BiometricReadRepository(Protocol):
    """Read access for current Garmin biometric marts."""

    def load_daily_metrics(self) -> list[DailyMetric]: ...

    def load_wellness(self, date: str | None = None) -> list[DayWellness]: ...

    def load_sleep(self, date: str | None = None) -> list[DaySleep]: ...

    def load_hrv(self, date: str | None = None) -> list[DayHrv]: ...

    def load_skin_temp(self, date: str | None = None) -> list[DaySkinTemp]: ...
