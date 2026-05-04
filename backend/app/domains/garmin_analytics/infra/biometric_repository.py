"""SQLite-backed Garmin biometric read repository."""

from app.infra.database import (
    load_daily_metrics,
    load_hrv,
    load_skin_temp,
    load_sleep,
    load_wellness,
)
from app.models import DailyMetric, DayHrv, DaySkinTemp, DaySleep, DayWellness


class SqliteBiometricRepository:
    """Adapter around the current ingested biometric tables."""

    def load_daily_metrics(self) -> list[DailyMetric]:
        return load_daily_metrics()

    def load_wellness(self, date: str | None = None) -> list[DayWellness]:
        return load_wellness(date)

    def load_sleep(self, date: str | None = None) -> list[DaySleep]:
        return load_sleep(date)

    def load_hrv(self, date: str | None = None) -> list[DayHrv]:
        return load_hrv(date)

    def load_skin_temp(self, date: str | None = None) -> list[DaySkinTemp]:
        return load_skin_temp(date)
