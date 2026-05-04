"""Tests for Garmin analytics biometric application use cases."""

import pytest

from app.models import (
    DailyAggregatesResponse,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
)


class _FakeBiometricRepository:
    def __init__(self):
        self.wellness: list[DayWellness] = []
        self.sleep: list[DaySleep] = []
        self.hrv: list[DayHrv] = []
        self.skin_temp: list[DaySkinTemp] = []
        self.daily = []

    def load_daily_metrics(self):
        return self.daily

    def load_wellness(self, date: str | None = None):
        return [day for day in self.wellness if date is None or day.date == date]

    def load_sleep(self, date: str | None = None):
        return [day for day in self.sleep if date is None or day.date == date]

    def load_hrv(self, date: str | None = None):
        return [day for day in self.hrv if date is None or day.date == date]

    def load_skin_temp(self, date: str | None = None):
        return [day for day in self.skin_temp if date is None or day.date == date]


def test_wellness_read_returns_flattened_day_payload():
    from app.domains.garmin_analytics.application.biometrics import get_wellness

    repo = _FakeBiometricRepository()
    repo.wellness = [DayWellness(date="2026-04-12")]

    response = get_wellness(repo)

    assert response.days == ["2026-04-12"]
    assert response.heart_rate == []


def test_date_filtered_biometric_read_raises_lookup_error_when_day_missing():
    from app.domains.garmin_analytics.application.biometrics import get_sleep

    repo = _FakeBiometricRepository()

    with pytest.raises(LookupError, match="Day 2026-04-12 not found"):
        get_sleep(repo, date="2026-04-12")


def test_daily_aggregates_include_windowed_period_summaries():
    from app.domains.garmin_analytics.application.biometrics import get_daily_aggregates

    repo = _FakeBiometricRepository()

    response = get_daily_aggregates(repo)

    assert isinstance(response, DailyAggregatesResponse)
    assert response.days == []
    assert response.daily == []
    assert set(response.period_windows) == {"3M", "6M", "All"}


def test_dashboard_overview_raises_lookup_error_when_metrics_missing():
    from app.domains.garmin_analytics.application.overview import get_dashboard_overview

    repo = _FakeBiometricRepository()

    with pytest.raises(LookupError, match="No data available"):
        get_dashboard_overview(repo)
