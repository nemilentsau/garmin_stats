"""Cross-domain read gateway for assistant evidence assembly.

The assistant application consumes read-model protocols without depending on
concrete domain adapters. Bootstrap injects already-built repositories here so
conversation persistence stays separate from evidence reads and cache refresh
policy.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.profile.contracts import UserProfile
from app.core.profile.ports import ProfileRepository
from app.domains.experiments.application.analysis_cache import (
    get_experiment_analysis as get_current_experiment_analysis,
)
from app.domains.experiments.application.analysis_cache import (
    refresh_active_experiment_analyses,
)
from app.domains.experiments.contracts import (
    Experiment,
    ExperimentAnalysis,
    ExperimentExposure,
)
from app.domains.experiments.dependencies import ExperimentRepository
from app.domains.garmin_analytics.application.dependencies import BiometricReadRepository
from app.domains.garmin_health.contracts import DailyMetric
from app.domains.journal.contracts import (
    DailyCheckIn,
    Note,
)
from app.domains.journal.dependencies import JournalRepository
from app.domains.routines.contracts import CardLog, RoutineAssignment, RoutineSchedule
from app.domains.routines.dependencies import RoutineRepository


@dataclass(frozen=True)
class AssistantReadModelGateway:
    """Assistant read dependency backed by already-composed domain repositories."""

    experiment_repo: ExperimentRepository
    profile_repo: ProfileRepository
    routine_repo: RoutineRepository
    journal_repo: JournalRepository
    biometric_repo: BiometricReadRepository

    def list_experiments(
        self,
        *,
        statuses: tuple[str, ...] | None = None,
    ) -> list[Experiment]:
        return self.experiment_repo.list_experiments(statuses=statuses)

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        return self.experiment_repo.get_experiment(experiment_id)

    def get_experiment_analysis(self, experiment_id: str) -> ExperimentAnalysis | None:
        try:
            return get_current_experiment_analysis(self.experiment_repo, experiment_id)
        except LookupError:
            return None

    def list_active_experiment_analyses(self) -> dict[str, ExperimentAnalysis]:
        """Return active experiment analyses via stale-gated bulk refresh."""
        return refresh_active_experiment_analyses(self.experiment_repo)

    def list_experiment_exposures(
        self,
        *,
        experiment_id: str | None = None,
        date: str | None = None,
    ) -> list[ExperimentExposure]:
        return self.experiment_repo.list_experiment_exposures(
            experiment_id=experiment_id, date=date,
        )

    def list_routines(self, *, status: str | None = None) -> list[RoutineSchedule]:
        return self.routine_repo.list_routines(status=status)

    def get_routine(self, routine_id: str) -> RoutineSchedule | None:
        return self.routine_repo.get_routine(routine_id)

    def list_assignments(
        self,
        *,
        routine_id: str | None = None,
    ) -> list[RoutineAssignment]:
        return self.routine_repo.list_assignments(routine_id=routine_id)

    def list_card_logs_range(self, *, start_date: str, end_date: str) -> list[CardLog]:
        return self.routine_repo.list_card_logs_range(
            start_date=start_date,
            end_date=end_date,
        )

    def list_recent_metrics(self, *, last_n: int | None = None) -> list[DailyMetric]:
        return self.biometric_repo.load_daily_metrics(last_n=last_n)

    def list_recent_checkins(self, *, last_n: int | None = None) -> list[DailyCheckIn]:
        return self.journal_repo.list_checkins(last_n=last_n)

    def list_recent_notes(self, *, last_n: int | None = None) -> list[Note]:
        return self.journal_repo.list_notes(last_n=last_n)

    def get_profile(self, profile_id: str = "default") -> UserProfile | None:
        return self.profile_repo.get_profile(profile_id=profile_id)
