"""Raw biometric table read use cases for Garmin analytics."""

from collections.abc import Sequence

from app.domains.garmin_analytics.application.dependencies import BiometricReadRepository
from app.domains.garmin_analytics.contracts import (
    HrvResponse,
    SkinTempResponse,
    SleepResponse,
    WellnessResponse,
)
from app.domains.garmin_analytics.domain.aggregates.biometric_responses import (
    flatten_hrv,
    flatten_skin_temp,
    flatten_sleep,
    flatten_wellness,
)


def _raise_if_missing(date: str | None, days: Sequence[object]) -> None:
    if date and not days:
        raise LookupError(f"Day {date} not found")


def get_wellness(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> WellnessResponse:
    days = repo.load_wellness(date)
    _raise_if_missing(date, days)
    return flatten_wellness(days)


def get_sleep(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> SleepResponse:
    days = repo.load_sleep(date)
    _raise_if_missing(date, days)
    return flatten_sleep(days)


def get_hrv(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> HrvResponse:
    days = repo.load_hrv(date)
    _raise_if_missing(date, days)
    return flatten_hrv(days)


def get_skin_temp(
    repo: BiometricReadRepository,
    date: str | None = None,
) -> SkinTempResponse:
    days = repo.load_skin_temp(date)
    _raise_if_missing(date, days)
    return flatten_skin_temp(days)
