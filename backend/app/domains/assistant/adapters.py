"""SQLite-backed assistant repository and read-model adapter.

This module owns assistant conversation persistence and the adapter boundary for
evidence reads from explicitly allowed domain read models. It keeps SQLite table
helpers and cross-domain read wiring out of the application layer.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.core.profile.contracts import UserProfile
from app.core.profile.ports import ProfileRepository
from app.domains.assistant.contracts import (
    AssistantEvidenceBundle,
    AssistantMemoryRecord,
    AssistantMessage,
    AssistantRun,
    AssistantThread,
    ContextSnapshot,
    EvidenceCard,
    Plan,
    PlanItem,
)
from app.domains.assistant.domain.text import normalize_alias
from app.domains.experiments.application.analysis_cache import (
    get_experiment_analysis as get_current_experiment_analysis,
)
from app.domains.experiments.contracts import (
    Experiment,
    ExperimentAnalysis,
    ExperimentExposure,
)
from app.domains.experiments.dependencies import ExperimentRepository
from app.domains.garmin_analytics.adapters import load_daily_metrics
from app.domains.garmin_health.contracts import DailyMetric
from app.domains.journal.adapters import (
    load_daily_checkins,
    load_notes,
)
from app.domains.journal.contracts import (
    DailyCheckIn,
    Note,
)
from app.domains.routines.adapters import (
    load_card_logs_range,
    load_routine_assignments,
    load_routine_schedules,
)
from app.domains.routines.contracts import CardLog, RoutineAssignment, RoutineSchedule
from app.infra.jsonstore import JsonStore
from app.infra.sqlite import connect
from app.utils.timeutil import now_iso

_STORE = JsonStore({
    "plans",
    "plan_items",
    "assistant_threads",
    "assistant_messages",
    "assistant_runs",
    "context_snapshots",
    "assistant_evidence_bundles",
    "assistant_memory_records",
    "evidence_cards",
})


def save_plan(plan: Plan) -> None:
    _STORE.save("plans", plan.id, plan.model_dump_json())


def load_plans() -> list[Plan]:
    return _STORE.load_many("plans", Plan)


def save_plan_item(item: PlanItem) -> None:
    _STORE.save(
        "plan_items",
        item.id,
        item.model_dump_json(),
        extra_columns={
            "plan_id": item.plan_id,
            "item_date": item.date,
        },
    )


def load_plan_items(plan_id: str | None = None) -> list[PlanItem]:
    where_sql = "plan_id = ?" if plan_id is not None else ""
    params = (plan_id,) if plan_id is not None else ()
    return _STORE.load_many(
        "plan_items",
        PlanItem,
        where_sql=where_sql,
        params=params,
        order_by="item_date, created_at, id",
    )


def create_assistant_thread(thread: AssistantThread) -> None:
    """Insert one new assistant thread and reject duplicate ids."""
    created_at = thread.created_at or now_iso()
    payload = thread.model_copy(update={"created_at": created_at}).model_dump_json()
    with connect() as con, con:
        try:
            con.execute(
                (
                    "INSERT INTO assistant_threads "
                    "(id, data, created_at, updated_at) VALUES (?, ?, ?, ?)"
                ),
                (thread.id, payload, created_at, created_at),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Assistant thread {thread.id} already exists") from exc


def save_assistant_thread(thread: AssistantThread) -> None:
    _STORE.save("assistant_threads", thread.id, thread.model_dump_json())


def load_assistant_thread(thread_id: str) -> AssistantThread | None:
    return _STORE.load("assistant_threads", AssistantThread, thread_id)


def load_assistant_threads() -> list[AssistantThread]:
    return _STORE.load_many("assistant_threads", AssistantThread)


def save_assistant_message(message: AssistantMessage) -> None:
    _STORE.save(
        "assistant_messages",
        message.id,
        message.model_dump_json(),
        extra_columns={"thread_id": message.thread_id},
        created_at=message.created_at,
    )


def load_assistant_messages(thread_id: str) -> list[AssistantMessage]:
    return _STORE.load_many(
        "assistant_messages",
        AssistantMessage,
        where_sql="thread_id = ?",
        params=(thread_id,),
        order_by="created_at, id",
    )


def save_assistant_run(run: AssistantRun) -> None:
    _STORE.save(
        "assistant_runs",
        run.id,
        run.model_dump_json(),
        extra_columns={"thread_id": run.thread_id},
        created_at=run.started_at,
        updated_at=run.finished_at or run.started_at,
    )


def finalize_assistant_reply(
    *,
    assistant_message: AssistantMessage,
    updated_thread: AssistantThread,
    completed_run: AssistantRun,
    memory_record: AssistantMemoryRecord | None = None,
) -> None:
    """Persist reply message, thread metadata, run state, and optional memory in one transaction."""
    with connect() as con, con:
        _STORE.save_in_connection(
            con,
            "assistant_messages",
            assistant_message.id,
            assistant_message.model_dump_json(),
            extra_columns={"thread_id": assistant_message.thread_id},
            created_at=assistant_message.created_at,
        )
        _STORE.save_in_connection(
            con,
            "assistant_threads",
            updated_thread.id,
            updated_thread.model_dump_json(),
        )
        _STORE.save_in_connection(
            con,
            "assistant_runs",
            completed_run.id,
            completed_run.model_dump_json(),
            extra_columns={"thread_id": completed_run.thread_id},
            created_at=completed_run.started_at,
            updated_at=completed_run.finished_at or completed_run.started_at,
        )
        if memory_record is not None:
            _STORE.save_in_connection(
                con,
                "assistant_memory_records",
                memory_record.id,
                memory_record.model_dump_json(),
                extra_columns={
                    "kind": memory_record.kind,
                    "entity_id": memory_record.entity_id,
                    "alias_text": memory_record.alias_text,
                    "alias_normalized": normalize_alias(memory_record.alias_text),
                },
                created_at=memory_record.created_at,
                updated_at=memory_record.updated_at or memory_record.created_at,
            )


def load_assistant_runs(thread_id: str | None = None) -> list[AssistantRun]:
    where_sql = "thread_id = ?" if thread_id is not None else ""
    params = (thread_id,) if thread_id is not None else ()
    return _STORE.load_many(
        "assistant_runs",
        AssistantRun,
        where_sql=where_sql,
        params=params,
        order_by="created_at, id",
    )


def save_assistant_evidence_bundle(bundle: AssistantEvidenceBundle) -> None:
    _STORE.save(
        "assistant_evidence_bundles",
        bundle.id,
        bundle.model_dump_json(),
        extra_columns={
            "thread_id": bundle.thread_id,
            "user_message_id": bundle.user_message_id,
            "intent": bundle.intent,
        },
        created_at=bundle.created_at,
        updated_at=bundle.updated_at,
    )


def load_assistant_evidence_bundles(
    thread_id: str | None = None,
    *,
    last_n: int | None = None,
) -> list[AssistantEvidenceBundle]:
    where_sql = "thread_id = ?" if thread_id is not None else ""
    params = (thread_id,) if thread_id is not None else ()
    return _STORE.load_many(
        "assistant_evidence_bundles",
        AssistantEvidenceBundle,
        where_sql=where_sql,
        params=params,
        order_by="created_at, id",
        last_n=last_n,
    )


def save_assistant_memory_record(record: AssistantMemoryRecord) -> None:
    """Persist one memory record alongside its alias_normalized lookup column."""
    _STORE.save(
        "assistant_memory_records",
        record.id,
        record.model_dump_json(),
        extra_columns={
            "kind": record.kind,
            "entity_id": record.entity_id,
            "alias_text": record.alias_text,
            "alias_normalized": normalize_alias(record.alias_text),
        },
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def load_assistant_memory_records(
    kind: str | None = None,
    *,
    last_n: int | None = None,
    alias_candidates: tuple[str, ...] | None = None,
) -> list[AssistantMemoryRecord]:
    clauses: list[str] = []
    params: list[object] = []
    if kind is not None:
        clauses.append("kind = ?")
        params.append(kind)

    normalized_candidates = tuple(
        normalized
        for normalized in (
            normalize_alias(candidate) for candidate in (alias_candidates or ())
        )
        if normalized is not None
    )
    if alias_candidates is not None:
        if not normalized_candidates:
            return []
        placeholders = ", ".join("?" for _ in normalized_candidates)
        clauses.append(f"alias_normalized IN ({placeholders})")
        params.extend(normalized_candidates)

    return _STORE.load_many(
        "assistant_memory_records",
        AssistantMemoryRecord,
        where_sql=" AND ".join(clauses),
        params=tuple(params),
        order_by="created_at, id",
        last_n=last_n,
    )


def save_context_snapshot(snapshot: ContextSnapshot) -> None:
    _STORE.save(
        "context_snapshots",
        snapshot.id,
        snapshot.model_dump_json(),
        created_at=snapshot.created_at,
    )


def load_context_snapshot(snapshot_id: str) -> ContextSnapshot | None:
    return _STORE.load("context_snapshots", ContextSnapshot, snapshot_id)


def load_context_snapshots() -> list[ContextSnapshot]:
    return _STORE.load_many("context_snapshots", ContextSnapshot)


def save_evidence_card(card: EvidenceCard) -> None:
    _STORE.save("evidence_cards", card.id, card.model_dump_json())


def load_evidence_cards() -> list[EvidenceCard]:
    return _STORE.load_many("evidence_cards", EvidenceCard)


@dataclass(frozen=True)
class SqliteAssistantRepository:
    """Repository adapter wired by bootstrap for assistant workflows."""

    experiment_repo: ExperimentRepository
    profile_repo: ProfileRepository

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
        return self.profile_repo.get_profile(profile_id=profile_id)
