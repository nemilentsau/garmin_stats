"""Dependencies consumed by assistant application use cases.

Assistant workflows split durable conversation writes from cross-domain
read-model access and the external chat runtime. Concrete SQLite reads, cache
behavior, and subprocess execution belong in assistant adapters/runtime.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any, Protocol

from app.core.profile.contracts import UserProfile
from app.domains.assistant.contracts import (
    AssistantEvidenceBundle,
    AssistantMemoryRecord,
    AssistantMessage,
    AssistantRun,
    AssistantThread,
)
from app.domains.experiments.contracts import (
    Experiment,
    ExperimentAnalysis,
    ExperimentExposure,
)
from app.domains.garmin_health.contracts import DailyMetric
from app.domains.journal.contracts import (
    DailyCheckIn,
    Note,
)
from app.domains.routines.contracts import CardLog, RoutineAssignment, RoutineSchedule


class AssistantConversationStore(Protocol):
    """Write-side dependency for assistant threads, messages, runs, and memory."""

    def list_threads(self) -> list[AssistantThread]: ...
    def get_thread(self, thread_id: str) -> AssistantThread | None: ...
    def create_thread(self, thread: AssistantThread) -> None: ...
    def save_thread(self, thread: AssistantThread) -> None: ...
    def list_messages(self, thread_id: str) -> list[AssistantMessage]: ...
    def save_message(self, message: AssistantMessage) -> None: ...
    def finalize_reply(
        self,
        *,
        assistant_message: AssistantMessage,
        updated_thread: AssistantThread,
        completed_run: AssistantRun,
        memory_record: AssistantMemoryRecord | None = None,
    ) -> None: ...
    def save_run(self, run: AssistantRun) -> None: ...
    def save_evidence_bundle(self, bundle: AssistantEvidenceBundle) -> None: ...
    def list_evidence_bundles(
        self,
        thread_id: str | None = None,
        *,
        last_n: int | None = None,
    ) -> list[AssistantEvidenceBundle]: ...
    def save_memory_record(self, record: AssistantMemoryRecord) -> None: ...
    def list_memory_records(
        self,
        kind: str | None = None,
        *,
        last_n: int | None = None,
        alias_candidates: tuple[str, ...] | None = None,
    ) -> list[AssistantMemoryRecord]: ...


class AssistantReadModelStore(Protocol):
    """Read dependency for evidence context assembled from owned domains."""

    def list_experiments(
        self,
        *,
        statuses: tuple[str, ...] | None = None,
    ) -> list[Experiment]: ...
    def get_experiment(self, experiment_id: str) -> Experiment | None: ...
    def get_experiment_analysis(self, experiment_id: str) -> ExperimentAnalysis | None: ...
    def list_active_experiment_analyses(self) -> dict[str, ExperimentAnalysis]: ...
    def list_experiment_exposures(
        self,
        *,
        experiment_id: str | None = None,
        date: str | None = None,
    ) -> list[ExperimentExposure]: ...
    def list_routines(self, *, status: str | None = None) -> list[RoutineSchedule]: ...
    def get_routine(self, routine_id: str) -> RoutineSchedule | None: ...
    def list_assignments(self, *, routine_id: str | None = None) -> list[RoutineAssignment]: ...
    def list_card_logs_range(self, *, start_date: str, end_date: str) -> list[CardLog]: ...
    def list_recent_metrics(self, *, last_n: int | None = None) -> list[DailyMetric]: ...
    def list_recent_checkins(self, *, last_n: int | None = None) -> list[DailyCheckIn]: ...
    def list_recent_notes(self, *, last_n: int | None = None) -> list[Note]: ...
    def get_profile(self, profile_id: str = "default") -> UserProfile | None: ...


class AssistantRecallStore(Protocol):
    """Read dependency for prior assistant evidence and memory records."""

    def list_evidence_bundles(
        self,
        thread_id: str | None = None,
        *,
        last_n: int | None = None,
    ) -> list[AssistantEvidenceBundle]: ...
    def list_memory_records(
        self,
        kind: str | None = None,
        *,
        last_n: int | None = None,
        alias_candidates: tuple[str, ...] | None = None,
    ) -> list[AssistantMemoryRecord]: ...


class AssistantRuntime(Protocol):
    """Streaming chat runtime dependency used after deterministic retrieval."""

    def stream_chat(
        self,
        *,
        evidence_bundle: AssistantEvidenceBundle,
        prior_messages: Sequence[AssistantMessage],
        memory_records: Sequence[AssistantMemoryRecord],
        user_message: str,
        model: str,
    ) -> AsyncIterator[dict[str, Any]]: ...
