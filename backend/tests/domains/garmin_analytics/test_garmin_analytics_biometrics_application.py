"""Tests for Garmin analytics biometric application use cases."""

import pytest

from app.domains.garmin_analytics.contracts import DailyAggregatesResponse
from app.domains.garmin_health.contracts import (
    BodyBatteryReading,
    DayHrv,
    DaySkinTemp,
    DaySleep,
    DayWellness,
    HeartRateReading,
    RespirationReading,
    RestingHRReading,
    SpO2Reading,
    StressReading,
)


class _FakeBiometricRepository:
    def __init__(self):
        self.wellness: list[DayWellness] = []
        self.sleep: list[DaySleep] = []
        self.hrv: list[DayHrv] = []
        self.skin_temp: list[DaySkinTemp] = []
        self.daily = []
        self.day_table_loads = 0

    def load_daily_metrics(self):
        return self.daily

    def load_wellness(self, date: str | None = None):
        self.day_table_loads += 1
        return [day for day in self.wellness if date is None or day.date == date]

    def load_sleep(self, date: str | None = None):
        self.day_table_loads += 1
        return [day for day in self.sleep if date is None or day.date == date]

    def load_hrv(self, date: str | None = None):
        self.day_table_loads += 1
        return [day for day in self.hrv if date is None or day.date == date]

    def load_skin_temp(self, date: str | None = None):
        self.day_table_loads += 1
        return [day for day in self.skin_temp if date is None or day.date == date]


def test_heart_rate_raw_read_returns_heart_rate_payload_only():
    from app.domains.garmin_analytics.application.raw_biometrics import get_heart_rate_raw

    repo = _FakeBiometricRepository()
    repo.wellness = [
        DayWellness(
            date="2026-04-12",
            heart_rate=[HeartRateReading(timestamp="2026-04-12T08:00:00", value=62)],
            resting_hr=[RestingHRReading(timestamp="2026-04-12T06:00:00", resting_hr=48)],
            stress=[StressReading(timestamp="2026-04-12T08:00:00", value=15)],
        ),
    ]

    response = get_heart_rate_raw(repo)

    assert response.days == ["2026-04-12"]
    assert [reading.value for reading in response.heart_rate] == [62]
    assert [reading.resting_hr for reading in response.resting_hr] == [48]
    assert not hasattr(response, "stress")


def test_stress_raw_read_returns_stress_payload_only():
    from app.domains.garmin_analytics.application.raw_biometrics import get_stress_raw

    repo = _FakeBiometricRepository()
    repo.wellness = [
        DayWellness(
            date="2026-04-12",
            heart_rate=[HeartRateReading(timestamp="2026-04-12T08:00:00", value=62)],
            stress=[StressReading(timestamp="2026-04-12T08:00:00", value=15)],
        ),
    ]

    response = get_stress_raw(repo)

    assert response.days == ["2026-04-12"]
    assert [reading.value for reading in response.stress] == [15]
    assert not hasattr(response, "heart_rate")


def test_body_battery_raw_read_returns_body_battery_payload_only():
    from app.domains.garmin_analytics.application.raw_biometrics import get_body_battery_raw

    repo = _FakeBiometricRepository()
    repo.wellness = [
        DayWellness(
            date="2026-04-12",
            body_battery=[BodyBatteryReading(timestamp="2026-04-12T08:00:00", value=77)],
            stress=[StressReading(timestamp="2026-04-12T08:00:00", value=15)],
        ),
    ]

    response = get_body_battery_raw(repo)

    assert response.days == ["2026-04-12"]
    assert [reading.value for reading in response.body_battery] == [77]
    assert not hasattr(response, "stress")


def test_spo2_raw_read_returns_spo2_payload_only():
    from app.domains.garmin_analytics.application.raw_biometrics import get_spo2_raw

    repo = _FakeBiometricRepository()
    repo.wellness = [
        DayWellness(
            date="2026-04-12",
            spo2=[SpO2Reading(timestamp="2026-04-12T08:00:00", value=96, mode="sleep")],
            respiration=[RespirationReading(timestamp="2026-04-12T08:00:00", value=14.0)],
        ),
    ]

    response = get_spo2_raw(repo)

    assert response.days == ["2026-04-12"]
    assert [reading.value for reading in response.spo2] == [96]
    assert not hasattr(response, "respiration")


def test_respiration_raw_read_returns_respiration_payload_only():
    from app.domains.garmin_analytics.application.raw_biometrics import get_respiration_raw

    repo = _FakeBiometricRepository()
    repo.wellness = [
        DayWellness(
            date="2026-04-12",
            spo2=[SpO2Reading(timestamp="2026-04-12T08:00:00", value=96, mode="sleep")],
            respiration=[RespirationReading(timestamp="2026-04-12T08:00:00", value=14.0)],
        ),
    ]

    response = get_respiration_raw(repo)

    assert response.days == ["2026-04-12"]
    assert [reading.value for reading in response.respiration] == [14.0]
    assert not hasattr(response, "spo2")


def test_date_filtered_biometric_read_raises_lookup_error_when_day_missing():
    from app.domains.garmin_analytics.application.raw_biometrics import get_sleep

    repo = _FakeBiometricRepository()

    with pytest.raises(LookupError, match="Day 2026-04-12 not found"):
        get_sleep(repo, date="2026-04-12")


def test_date_filtered_raw_metric_read_raises_lookup_error_when_day_missing():
    from app.domains.garmin_analytics.application.raw_biometrics import get_heart_rate_raw

    repo = _FakeBiometricRepository()

    with pytest.raises(LookupError, match="Day 2026-04-12 not found"):
        get_heart_rate_raw(repo, date="2026-04-12")


def test_daily_aggregates_include_windowed_period_summaries():
    from app.domains.garmin_analytics.application.daily_aggregates import get_daily_aggregates

    repo = _FakeBiometricRepository()

    response = get_daily_aggregates(repo)

    assert isinstance(response, DailyAggregatesResponse)
    assert response.days == []
    assert response.daily == []
    assert set(response.period_windows) == {"3M", "6M", "All"}


def test_daily_aggregates_reuse_cached_period_summaries_when_unchanged():
    from app.domains.garmin_analytics.application.daily_aggregates import get_daily_aggregates

    repo = _FakeBiometricRepository()

    get_daily_aggregates(repo)
    first_load_count = repo.day_table_loads

    get_daily_aggregates(repo)

    assert first_load_count == 4
    assert repo.day_table_loads == first_load_count


def test_dashboard_overview_raises_lookup_error_when_metrics_missing():
    from app.domains.garmin_analytics.application.dashboard import get_dashboard_overview

    repo = _FakeBiometricRepository()

    with pytest.raises(LookupError, match="No data available"):
        get_dashboard_overview(repo)
