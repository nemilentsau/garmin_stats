"""Raw biometric table read use cases for Garmin analytics.

This layer owns date filtering and missing-date behavior for raw metric
endpoints. It delegates response shaping to pure aggregate helpers.
"""

from collections.abc import Sequence

from app.domains.garmin_analytics.application.dependencies import BiometricReadRepository
from app.domains.garmin_analytics.contracts import (
    BodyBatteryRawResponse,
    HeartRateRawResponse,
    HrvResponse,
    RespirationRawResponse,
    SkinTempResponse,
    SleepResponse,
    SpO2RawResponse,
    StressRawResponse,
)
from app.domains.garmin_analytics.domain.aggregates.biometric_responses import (
    flatten_body_battery,
    flatten_heart_rate,
    flatten_hrv,
    flatten_respiration,
    flatten_skin_temp,
    flatten_sleep,
    flatten_spo2,
    flatten_stress,
)
from app.domains.garmin_health.contracts import DayWellness


def _raise_if_missing(date: str | None, days: Sequence[object]) -> None:
    if date and not days:
        raise LookupError(f"Day {date} not found")


def _load_wellness(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> list[DayWellness]:
    days = repo.load_wellness(date)
    _raise_if_missing(date, days)
    return days


def get_heart_rate_raw(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> HeartRateRawResponse:
    """Return flattened heart-rate readings for all days or one date."""
    return flatten_heart_rate(_load_wellness(repo, date))


def get_stress_raw(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> StressRawResponse:
    """Return flattened stress readings for all days or one date."""
    return flatten_stress(_load_wellness(repo, date))


def get_body_battery_raw(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> BodyBatteryRawResponse:
    """Return flattened Body Battery readings for all days or one date."""
    return flatten_body_battery(_load_wellness(repo, date))


def get_spo2_raw(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> SpO2RawResponse:
    """Return flattened SpO2 readings for all days or one date."""
    return flatten_spo2(_load_wellness(repo, date))


def get_respiration_raw(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> RespirationRawResponse:
    """Return flattened respiration readings for all days or one date."""
    return flatten_respiration(_load_wellness(repo, date))


def get_sleep(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> SleepResponse:
    """Return flattened sleep rows for all days or one date."""
    days = repo.load_sleep(date)
    _raise_if_missing(date, days)
    return flatten_sleep(days)


def get_hrv(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> HrvResponse:
    """Return flattened HRV rows for all days or one date."""
    days = repo.load_hrv(date)
    _raise_if_missing(date, days)
    return flatten_hrv(days)


def get_skin_temp(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> SkinTempResponse:
    """Return flattened skin-temperature rows for all days or one date."""
    days = repo.load_skin_temp(date)
    _raise_if_missing(date, days)
    return flatten_skin_temp(days)
