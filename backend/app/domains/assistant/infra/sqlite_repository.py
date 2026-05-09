"""SQLite repository adapter for assistant conversation and read-model stores."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.profile.contracts import UserProfile
from app.domains.assistant.application.types import AssistantEvidenceBundle, AssistantMemoryRecord
from app.domains.assistant.contracts import (
    AssistantMessage,
    AssistantRun,
    AssistantThread,
)
from app.domains.experiments.application.analysis_cache import (
    get_experiment_analysis as get_current_experiment_analysis,
)
from app.domains.experiments.application.ports import ExperimentRepository
from app.domains.experiments.contracts import (
    Experiment,
    ExperimentAnalysis,
    ExperimentExposure,
)
from app.domains.garmin_analytics.adapters import load_daily_metrics
from app.domains.garmin_analytics.contracts import DailyMetric
from app.domains.journal.contracts import (
    DailyCheckIn,
    Note,
)
from app.domains.routines.contracts import CardLog, RoutineAssignment, RoutineSchedule
from app.infra.database import (
    create_assistant_thread,
    finalize_assistant_reply,
    load_assistant_evidence_bundles,
    load_assistant_memory_records,
    load_assistant_messages,
    load_assistant_thread,
    load_assistant_threads,
    load_card_logs_range,
    load_daily_checkins,
    load_notes,
    load_routine_assignments,
    load_routine_schedules,
    load_user_profile,
    save_assistant_evidence_bundle,
    save_assistant_memory_record,
    save_assistant_message,
    save_assistant_run,
    save_assistant_thread,
)


@dataclass(frozen=True)
class SqliteAssistantRepository:
    experiment_repo: ExperimentRepository

    def list_threads(self) -> list[AssistantThread]:
        return load_assistant_threads()

    def get_thread(self, thread_id: str) -> AssistantThread | None:
        return load_assistant_thread(thread_id)

    def create_thread(self, thread: AssistantThread) -> None:
        create_assistant_thread(thread)

    def save_thread(self, thread: AssistantThread) -> None:
        save_assistant_thread(thread)

    def list_messages(self, thread_id: str) -> list[AssistantMessage]:
        return load_assistant_messages(thread_id)

    def save_message(self, message: AssistantMessage) -> None:
        save_assistant_message(message)

    def finalize_reply(
        self,
        *,
        assistant_message: AssistantMessage,
        updated_thread: AssistantThread | dict[str, object],
        completed_run: AssistantRun,
        memory_record: AssistantMemoryRecord | None = None,
    ) -> None:
        thread = (
            AssistantThread.model_validate(updated_thread)
            if isinstance(updated_thread, dict)
            else updated_thread
        )
        finalize_assistant_reply(
            assistant_message=assistant_message,
            updated_thread=thread,
            completed_run=completed_run,
            memory_record=memory_record,
        )

    def save_run(self, run: AssistantRun) -> None:
        save_assistant_run(run)

    def save_evidence_bundle(self, bundle: AssistantEvidenceBundle) -> None:
        save_assistant_evidence_bundle(bundle)

    def list_evidence_bundles(
        self,
        thread_id: str | None = None,
        *,
        last_n: int | None = None,
    ) -> list[AssistantEvidenceBundle]:
        return load_assistant_evidence_bundles(thread_id=thread_id, last_n=last_n)

    def save_memory_record(self, record: AssistantMemoryRecord) -> None:
        save_assistant_memory_record(record)

    def list_memory_records(
        self,
        kind: str | None = None,
        *,
        last_n: int | None = None,
        alias_candidates: tuple[str, ...] | None = None,
    ) -> list[AssistantMemoryRecord]:
        return load_assistant_memory_records(
            kind=kind,
            last_n=last_n,
            alias_candidates=alias_candidates,
        )

    def list_experiments(
        self,
        *,
        statuses: tuple[str, ...] | None = None,
    ) -> list[Experiment]:
        return self.experiment_repo.list_experiments(statuses=statuses)

    def get_experiment_analysis(self, experiment_id: str) -> ExperimentAnalysis | None:
        try:
            return get_current_experiment_analysis(self.experiment_repo, experiment_id)
        except LookupError:
            return None

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
        return load_routine_schedules(status=status)

    def list_assignments(self, *, routine_id: str | None = None) -> list[RoutineAssignment]:
        return load_routine_assignments(routine_id=routine_id)

    def list_card_logs_range(self, *, start_date: str, end_date: str) -> list[CardLog]:
        return load_card_logs_range(start_date, end_date)

    def list_recent_metrics(self, *, last_n: int | None = None) -> list[DailyMetric]:
        metrics = load_daily_metrics()
        if last_n is None:
            return metrics
        if last_n <= 0:
            return []
        return metrics[-last_n:]

    def list_recent_checkins(self, *, last_n: int | None = None) -> list[DailyCheckIn]:
        return load_daily_checkins(last_n=last_n)

    def list_recent_notes(self, *, last_n: int | None = None) -> list[Note]:
        return load_notes(last_n=last_n)

    def get_profile(self, profile_id: str = "default") -> UserProfile | None:
        return load_user_profile(profile_id=profile_id)
