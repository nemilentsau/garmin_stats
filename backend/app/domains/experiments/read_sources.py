"""Read-model inputs for experiment analysis and preview workflows.

Experiments own definitions, exposures, and cached analyses. Garmin daily
metrics and journal check-ins remain owned by their domains, so bootstrap
injects those repositories here instead of letting experiment persistence import
concrete adapters from other slices.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domains.garmin_analytics.application.dependencies import BiometricReadRepository
from app.domains.garmin_health.contracts import DailyMetric
from app.domains.journal.contracts import DailyCheckIn
from app.domains.journal.dependencies import JournalRepository


@dataclass(frozen=True)
class ExperimentReadSource:
    """Experiment read source backed by already-composed domain repositories."""

    biometric_repo: BiometricReadRepository
    journal_repo: JournalRepository

    def list_daily_metrics(self) -> list[DailyMetric]:
        return self.biometric_repo.load_daily_metrics()

    def list_daily_checkins(self) -> list[DailyCheckIn]:
        return self.journal_repo.list_checkins()
