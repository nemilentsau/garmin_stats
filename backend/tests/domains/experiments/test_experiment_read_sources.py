"""Experiment read-source tests for Garmin metrics and journal check-ins."""

from typing import Any, cast

from app.domains.experiments.read_sources import ExperimentReadSource
from app.domains.garmin_health.contracts import DailyMetric
from app.domains.journal.contracts import DailyCheckIn


def test_read_source_loads_daily_metrics_from_biometric_repository():
    metric = cast(DailyMetric, object())

    class _BiometricRepo:
        def __init__(self):
            self.calls = 0

        def load_daily_metrics(self) -> list[DailyMetric]:
            self.calls += 1
            return [metric]

    class _JournalRepo:
        def list_checkins(self) -> list[DailyCheckIn]:
            raise AssertionError("metric reads should not load check-ins")

    biometric_repo = _BiometricRepo()
    source = ExperimentReadSource(
        biometric_repo=cast(Any, biometric_repo),
        journal_repo=cast(Any, _JournalRepo()),
    )

    assert source.list_daily_metrics() == [metric]
    assert biometric_repo.calls == 1


def test_read_source_loads_daily_checkins_from_journal_repository():
    checkin = cast(DailyCheckIn, object())

    class _BiometricRepo:
        def load_daily_metrics(self) -> list[DailyMetric]:
            raise AssertionError("check-in reads should not load metrics")

    class _JournalRepo:
        def __init__(self):
            self.calls = 0

        def list_checkins(self) -> list[DailyCheckIn]:
            self.calls += 1
            return [checkin]

    journal_repo = _JournalRepo()
    source = ExperimentReadSource(
        biometric_repo=cast(Any, _BiometricRepo()),
        journal_repo=cast(Any, journal_repo),
    )

    assert source.list_daily_checkins() == [checkin]
    assert journal_repo.calls == 1
