"""Tests for assistant chat application orchestration."""

import asyncio
import json
from typing import Any, cast

from app.domains.assistant.application.chat import stream_reply
from app.domains.assistant.application.types import AssistantEvidenceBundle, AssistantMemoryRecord
from app.models import (
    AssistantMessageCreateRequest,
    AssistantRun,
    CardLog,
    DailyCheckIn,
    DailyMetric,
    Experiment,
    ExperimentAnalysis,
    ExperimentExposure,
    Note,
    RoutineAssignment,
    RoutineSchedule,
    UserProfile,
)


async def _collect(stream):
    events = []
    async for event in stream:
        events.append(event)
    return events


class _FakeRuntime:
    def __init__(self, deltas: list[str], *, done_session_id: str | None = None):
        self._deltas = list(deltas)
        self._done_session_id = done_session_id
        self.stream_chat_kwargs: list[dict[str, object]] = []

    async def stream_chat(self, **_kwargs):
        self.stream_chat_kwargs.append(dict(_kwargs))
        for delta in self._deltas:
            yield {"type": "delta", "text": delta}
        yield {"type": "done", "session_id": self._done_session_id}


class _FakeConversationStore:
    def __init__(
        self,
        *,
        thread_id: str,
        claude_session_id: str | None,
        model: str = "sonnet",
        prior_messages: list[dict[str, Any]] | None = None,
        memory_records: list[AssistantMemoryRecord] | None = None,
        prior_evidence_bundles: list[AssistantEvidenceBundle] | None = None,
        fail_on_save_evidence_bundle: bool = False,
        fail_on_save_assistant_message: bool = False,
    ) -> None:
        self.thread_id = thread_id
        self.claude_session_id = claude_session_id
        self.model = model
        self.fail_on_save_evidence_bundle = fail_on_save_evidence_bundle
        self.fail_on_save_assistant_message = fail_on_save_assistant_message
        self.thread_state: dict[str, Any] = {
            "id": thread_id,
            "model": model,
            "claude_session_id": claude_session_id,
        }
        self.messages: list[object] = list(prior_messages or [])
        self.memory_records: list[AssistantMemoryRecord] = list(memory_records or [])
        self.prior_evidence_bundles: list[AssistantEvidenceBundle] = list(
            prior_evidence_bundles or []
        )
        self.saved_threads: list[dict[str, Any]] = []
        self.saved_evidence_bundles: list[AssistantEvidenceBundle] = []
        self.saved_runs: list[AssistantRun] = []

    @classmethod
    def with_thread(
        cls,
        *,
        thread_id: str,
        claude_session_id: str | None = None,
        model: str = "sonnet",
        prior_messages: list[dict[str, Any]] | None = None,
        memory_records: list[AssistantMemoryRecord] | None = None,
        fail_on_save_evidence_bundle: bool = False,
        fail_on_save_assistant_message: bool = False,
    ):
        return cls(
            thread_id=thread_id,
            claude_session_id=claude_session_id,
            model=model,
            prior_messages=prior_messages,
            memory_records=memory_records,
            fail_on_save_evidence_bundle=fail_on_save_evidence_bundle,
            fail_on_save_assistant_message=fail_on_save_assistant_message,
        )

    def get_thread(self, thread_id: str):
        if thread_id != self.thread_id:
            return None
        return dict(self.thread_state)

    def list_messages(self, thread_id: str):
        if thread_id != self.thread_id:
            return []
        return list(self.messages)

    def save_message(self, message):
        if getattr(message, "role", None) == "assistant" and self.fail_on_save_assistant_message:
            raise RuntimeError("assistant save failed")
        self.messages.append(message)

    def save_thread(self, thread):
        if not isinstance(thread, dict):
            raise TypeError("expected dict-backed thread in test fake")
        self.thread_state = dict(thread)
        self.saved_threads.append(dict(thread))

    def save_run(self, run):
        self.saved_runs.append(run)

    def save_evidence_bundle(self, bundle):
        if self.fail_on_save_evidence_bundle:
            raise RuntimeError("evidence save failed")
        self.saved_evidence_bundles.append(bundle)

    def list_evidence_bundles(
        self,
        thread_id: str | None = None,
        *,
        last_n: int | None = None,
    ):
        bundles = list(self.prior_evidence_bundles) + list(self.saved_evidence_bundles)
        if thread_id is not None:
            bundles = [bundle for bundle in bundles if bundle.thread_id == thread_id]
        if last_n is not None:
            bundles = bundles[-last_n:]
        return bundles

    def list_memory_records(
        self,
        kind: str | None = None,
        *,
        last_n: int | None = None,
    ):
        records = list(self.memory_records)
        if kind is not None:
            records = [record for record in records if record.kind == kind]
        if last_n is not None:
            records = records[-last_n:]
        return records


class _FakeReadStore:
    def __init__(
        self,
        *,
        experiments: list[Experiment],
        analysis_by_experiment_id: dict[str, ExperimentAnalysis],
        exposures_by_experiment_id: dict[str, list[ExperimentExposure]],
        routines: list[RoutineSchedule],
    ) -> None:
        self._experiments = list(experiments)
        self._analysis_by_experiment_id = dict(analysis_by_experiment_id)
        self._exposures_by_experiment_id = {
            experiment_id: list(exposures)
            for experiment_id, exposures in exposures_by_experiment_id.items()
        }
        self._routines = list(routines)

    @classmethod
    def for_experiment_review(cls):
        experiment = Experiment(
            id="meditation-hrv-2026-03",
            name="Meditation to HRV",
            status="active",
            linked_routine_ids=["meditation-routine"],
        )
        analysis = ExperimentAnalysis(
            experiment_id=experiment.id,
            analysis_date="2026-03-14",
            phase="treatment",
            days_in_baseline=14,
            days_in_treatment=14,
            adherence_rate=0.86,
            adherence_by_day=[],
            metrics=[],
            confounders=[],
            overall_confidence="moderate",
            summary="HRV trend improved while adherence remained stable.",
        )
        exposures = [
            ExperimentExposure(
                id="exp-1",
                experiment_id=experiment.id,
                date="2026-03-13",
                exposure_score=1.0,
                adherence_state="full",
            )
        ]
        routine = RoutineSchedule(
            id="meditation-routine",
            name="Meditation Session",
            status="active",
            start_date="2026-03-01",
        )
        return cls(
            experiments=[experiment],
            analysis_by_experiment_id={experiment.id: analysis},
            exposures_by_experiment_id={experiment.id: exposures},
            routines=[routine],
        )

    def list_experiments(
        self,
        *,
        status: str | None = None,
        statuses: tuple[str, ...] | None = None,
    ) -> list[Experiment]:
        experiments = list(self._experiments)
        if statuses is not None:
            return [experiment for experiment in experiments if experiment.status in statuses]
        if status is not None:
            return [experiment for experiment in experiments if experiment.status == status]
        return experiments

    def get_experiment_analysis(self, experiment_id: str) -> ExperimentAnalysis | None:
        return self._analysis_by_experiment_id.get(experiment_id)

    def list_experiment_exposures(
        self,
        *,
        experiment_id: str | None = None,
        date: str | None = None,
    ) -> list[ExperimentExposure]:
        if experiment_id is None:
            return []
        exposures = list(self._exposures_by_experiment_id.get(experiment_id, []))
        if date is None:
            return exposures
        return [exposure for exposure in exposures if exposure.date == date]

    def list_routines(self, *, status: str | None = None) -> list[RoutineSchedule]:
        routines = list(self._routines)
        if status is None:
            return routines
        return [routine for routine in routines if routine.status == status]

    def list_assignments(self, *, routine_id: str | None = None) -> list[RoutineAssignment]:
        _ = routine_id
        return []

    def list_card_logs_range(self, *, start_date: str, end_date: str) -> list[CardLog]:
        _ = (start_date, end_date)
        return []

    def list_recent_metrics(self, *, last_n: int | None = None) -> list[DailyMetric]:
        _ = last_n
        return []

    def list_recent_checkins(self, *, last_n: int | None = None) -> list[DailyCheckIn]:
        _ = last_n
        return []

    def list_recent_notes(self, *, last_n: int | None = None) -> list[Note]:
        _ = last_n
        return []

    def get_profile(self, profile_id: str = "default") -> UserProfile | None:
        _ = profile_id
        return None


def test_stream_reply_emits_fast_grounded_first_delta_before_runtime_tokens():
    repo = _FakeConversationStore.with_thread(
        thread_id="thread-1",
        memory_records=[
            AssistantMemoryRecord(
                id="memory-1",
                kind="entity_alias",
                entity_id="meditation-hrv-2026-03",
                alias_text="mindfulness protocol",
            )
        ],
    )
    runtime = _FakeRuntime(
        deltas=["I see adherence consistency across your recent days."],
        done_session_id="session-1",
    )

    lines = asyncio.run(
        _collect(
            stream_reply(
                repo=cast(Any, repo),
                read_store=_FakeReadStore.for_experiment_review(),
                runtime=cast(Any, runtime),
                thread_id="thread-1",
                request=AssistantMessageCreateRequest(
                    id="message-1",
                    content="How does our meditation experiment look like so far?",
                ),
            )
        )
    )

    payloads = [json.loads(line) for line in lines]
    assert payloads[0]["type"] == "delta"
    assert "Meditation" in payloads[0]["text"]
    assert payloads[-1]["type"] == "done"
    assert payloads[-1]["snapshot_id"] == repo.saved_evidence_bundles[0].id
    assert payloads[-1]["run_id"].startswith("run-")
    assert payloads[-1]["session_id"] == "session-1"
    assert repo.saved_evidence_bundles[0].intent == "experiment_review"
    assert len(runtime.stream_chat_kwargs) == 1
    evidence_bundle = runtime.stream_chat_kwargs[0]["evidence_bundle"]
    assert isinstance(evidence_bundle, AssistantEvidenceBundle)
    assert evidence_bundle.intent == "experiment_review"
    memory_records = runtime.stream_chat_kwargs[0]["memory_records"]
    assert isinstance(memory_records, list)
    assert memory_records
    assert isinstance(memory_records[0], AssistantMemoryRecord)
    assert memory_records[0].kind == "entity_alias"
    assert repo.saved_runs[-1].status == "completed"
    user_message = cast(Any, repo.messages[0])
    assistant_message = cast(Any, repo.messages[-1])
    assert repo.saved_threads[0]["last_message_at"] == user_message.created_at
    assert repo.saved_threads[-1]["last_message_at"] == assistant_message.created_at
    assert repo.saved_threads[-1]["last_context_snapshot_id"] == repo.saved_evidence_bundles[0].id
    assert repo.saved_threads[-1]["claude_session_id"] == "session-1"


def test_follow_up_works_without_claude_resume():
    seeded_prior_messages = (
        {
            "id": "message-1",
            "role": "user",
            "content_markdown": "Let's keep me moving this week.",
            "created_at": "2026-04-10T09:00:00Z",
        },
        {
            "id": "assistant-1",
            "role": "assistant",
            "content_markdown": "Try 20-minute walks.",
            "created_at": "2026-04-10T09:05:00Z",
        },
    )
    repo = _FakeConversationStore.with_thread(
        thread_id="thread-1",
        claude_session_id="stale-session-id",
        prior_messages=list(seeded_prior_messages),
    )
    runtime = _FakeRuntime(deltas=["You should keep going."])

    lines = asyncio.run(
        _collect(
            stream_reply(
                repo=cast(Any, repo),
                read_store=_FakeReadStore.for_experiment_review(),
                runtime=cast(Any, runtime),
                thread_id="thread-1",
                request=AssistantMessageCreateRequest(
                    id="message-2",
                    content="Any suggestions for me",
                ),
            )
        )
    )

    payloads = [json.loads(line) for line in lines]
    assert payloads[-1]["type"] == "done"
    assert "keep going" in payloads[-1]["message"]["content_markdown"].lower()
    assert len(runtime.stream_chat_kwargs) == 1
    assert runtime.stream_chat_kwargs[0]["prior_messages"] == [
        dict(message) for message in seeded_prior_messages
    ]
    assert "claude_session_id" not in runtime.stream_chat_kwargs[0]
    assert "session_id" not in runtime.stream_chat_kwargs[0]
    assert not any("resume" in str(key).lower() for key in runtime.stream_chat_kwargs[0])


def test_stream_reply_setup_failure_before_runtime_emits_error_and_marks_run_failed():
    repo = _FakeConversationStore.with_thread(
        thread_id="thread-1",
        fail_on_save_evidence_bundle=True,
    )
    runtime = _FakeRuntime(deltas=["should not stream"])

    lines = asyncio.run(
        _collect(
            stream_reply(
                repo=cast(Any, repo),
                read_store=_FakeReadStore.for_experiment_review(),
                runtime=cast(Any, runtime),
                thread_id="thread-1",
                request=AssistantMessageCreateRequest(
                    id="message-3",
                    content="How does our meditation experiment look like so far?",
                ),
            )
        )
    )

    payloads = [json.loads(line) for line in lines]
    assert payloads[-1]["type"] == "error"
    assert payloads[-1]["run_id"].startswith("run-")
    assert repo.saved_runs[-1].status == "failed"
    assert runtime.stream_chat_kwargs == []


def test_stream_reply_final_persistence_failure_emits_error_and_marks_run_failed():
    repo = _FakeConversationStore.with_thread(
        thread_id="thread-1",
        fail_on_save_assistant_message=True,
    )
    runtime = _FakeRuntime(deltas=["runtime answer"], done_session_id="session-final")

    lines = asyncio.run(
        _collect(
            stream_reply(
                repo=cast(Any, repo),
                read_store=_FakeReadStore.for_experiment_review(),
                runtime=cast(Any, runtime),
                thread_id="thread-1",
                request=AssistantMessageCreateRequest(
                    id="message-4",
                    content="How does our meditation experiment look like so far?",
                ),
            )
        )
    )

    payloads = [json.loads(line) for line in lines]
    assert payloads[-1]["type"] == "error"
    assert payloads[-1]["run_id"].startswith("run-")
    assert repo.saved_runs[-1].status == "failed"
