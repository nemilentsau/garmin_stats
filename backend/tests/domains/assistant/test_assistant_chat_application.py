"""Tests for assistant chat application orchestration."""

import asyncio
import json
from typing import Any, cast

from app.domains.assistant.application.chat import stream_reply
from app.domains.assistant.application.types import AssistantEvidenceBundle, AssistantMemoryRecord
from app.domains.garmin_analytics.contracts import DailyMetric
from app.models import (
    AssistantMessageCreateRequest,
    AssistantRun,
    CardLog,
    DailyCheckIn,
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
        fail_on_list_memory_records: bool = False,
        fail_on_finalize_reply: bool = False,
    ) -> None:
        self.thread_id = thread_id
        self.claude_session_id = claude_session_id
        self.model = model
        self.fail_on_save_evidence_bundle = fail_on_save_evidence_bundle
        self.fail_on_list_memory_records = fail_on_list_memory_records
        self.fail_on_finalize_reply = fail_on_finalize_reply
        self.thread_state: dict[str, Any] = {
            "id": thread_id,
            "model": model,
            "claude_session_id": claude_session_id,
        }
        self.messages: list[object] = list(prior_messages or [])
        self.memory_records: list[AssistantMemoryRecord] = list(memory_records or [])
        self.saved_memory_records: list[AssistantMemoryRecord] = []
        self.prior_evidence_bundles: list[AssistantEvidenceBundle] = list(
            prior_evidence_bundles or []
        )
        self.saved_threads: list[dict[str, Any]] = []
        self.saved_evidence_bundles: list[AssistantEvidenceBundle] = []
        self.saved_runs: list[AssistantRun] = []
        self.list_memory_calls: list[dict[str, object]] = []

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
        fail_on_list_memory_records: bool = False,
        fail_on_finalize_reply: bool = False,
    ):
        return cls(
            thread_id=thread_id,
            claude_session_id=claude_session_id,
            model=model,
            prior_messages=prior_messages,
            memory_records=memory_records,
            fail_on_save_evidence_bundle=fail_on_save_evidence_bundle,
            fail_on_list_memory_records=fail_on_list_memory_records,
            fail_on_finalize_reply=fail_on_finalize_reply,
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
        self.messages.append(message)

    def save_thread(self, thread):
        if not isinstance(thread, dict):
            raise TypeError("expected dict-backed thread in test fake")
        self.thread_state = dict(thread)
        self.saved_threads.append(dict(thread))

    def save_run(self, run):
        self.saved_runs.append(run)

    def finalize_reply(
        self,
        *,
        assistant_message,
        updated_thread,
        completed_run,
        memory_record=None,
    ):
        if self.fail_on_finalize_reply:
            raise RuntimeError("finalize reply failed")
        self.messages.append(assistant_message)
        self.save_thread(updated_thread)
        self.saved_runs.append(completed_run)
        if memory_record is not None:
            self.save_memory_record(memory_record)

    def save_evidence_bundle(self, bundle):
        if self.fail_on_save_evidence_bundle:
            raise RuntimeError("evidence save failed")
        self.saved_evidence_bundles.append(bundle)

    def save_memory_record(self, record: AssistantMemoryRecord) -> None:
        self.memory_records.append(record)
        self.saved_memory_records.append(record)

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
        alias_candidates: tuple[str, ...] | None = None,
    ):
        if self.fail_on_list_memory_records:
            raise RuntimeError("memory read failed")
        self.list_memory_calls.append(
            {
                "kind": kind,
                "last_n": last_n,
                "alias_candidates": alias_candidates,
            }
        )
        records = list(self.memory_records)
        if kind is not None:
            records = [record for record in records if record.kind == kind]
        if alias_candidates is not None:
            candidate_set = set(alias_candidates)
            records = [
                record
                for record in records
                if record.alias_text is not None
                and " ".join(record.alias_text.lower().split()) in candidate_set
            ]
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
    assert "refine this with your thread history" not in payloads[0]["text"]
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
    assert repo.saved_memory_records == []
    user_message = cast(Any, repo.messages[0])
    assistant_message = cast(Any, repo.messages[-1])
    assert repo.saved_threads[0]["last_message_at"] == user_message.created_at
    assert repo.saved_threads[-1]["last_message_at"] == assistant_message.created_at
    assert repo.saved_threads[-1]["last_context_snapshot_id"] == repo.saved_evidence_bundles[0].id
    assert repo.saved_threads[-1]["claude_session_id"] == "session-1"


def test_stream_reply_persists_confident_entity_alias_memory_for_short_experiment_alias():
    repo = _FakeConversationStore.with_thread(
        thread_id="thread-1",
    )
    runtime = _FakeRuntime(deltas=["I see a stable pattern."])

    lines = asyncio.run(
        _collect(
            stream_reply(
                repo=cast(Any, repo),
                read_store=_FakeReadStore.for_experiment_review(),
                runtime=cast(Any, runtime),
                thread_id="thread-1",
                request=AssistantMessageCreateRequest(
                    id="message-5",
                    content="Meditation to HRV",
                ),
            )
        )
    )

    payloads = [json.loads(line) for line in lines]
    assert payloads[-1]["type"] == "done"
    assert len(repo.saved_memory_records) == 1
    record = repo.saved_memory_records[0]
    assert record.kind == "entity_alias"
    assert record.entity_id == "meditation-hrv-2026-03"
    assert record.alias_text == "Meditation to HRV"
    memory_records = runtime.stream_chat_kwargs[0]["memory_records"]
    assert isinstance(memory_records, list)
    assert not any(
        isinstance(memory_record, AssistantMemoryRecord)
        and memory_record.kind == "entity_alias"
        and memory_record.alias_text == "Meditation to HRV"
        for memory_record in memory_records
    )


def test_stream_reply_reroutes_to_experiment_review_from_saved_alias_memory():
    repo = _FakeConversationStore.with_thread(
        thread_id="thread-1",
        memory_records=[
            AssistantMemoryRecord(
                id="memory-2",
                kind="entity_alias",
                entity_id="meditation-hrv-2026-03",
                alias_text="sleep stack",
            )
        ],
    )
    runtime = _FakeRuntime(deltas=["I see the treatment window clearly."])

    lines = asyncio.run(
        _collect(
            stream_reply(
                repo=cast(Any, repo),
                read_store=_FakeReadStore.for_experiment_review(),
                runtime=cast(Any, runtime),
                thread_id="thread-1",
                request=AssistantMessageCreateRequest(
                    id="message-6",
                    content="sleep stack",
                ),
            )
        )
    )

    payloads = [json.loads(line) for line in lines]
    assert payloads[-1]["type"] == "done"
    evidence_bundle = runtime.stream_chat_kwargs[0]["evidence_bundle"]
    assert isinstance(evidence_bundle, AssistantEvidenceBundle)
    assert evidence_bundle.intent == "experiment_review"
    assert any(entity.entity_id == "meditation-hrv-2026-03" for entity in evidence_bundle.entities)


def test_stream_reply_alias_reroute_uses_saved_alias_outside_prompt_memory_window():
    repo = _FakeConversationStore.with_thread(
        thread_id="thread-1",
        memory_records=[
            AssistantMemoryRecord(
                id="memory-target",
                kind="entity_alias",
                entity_id="meditation-hrv-2026-03",
                alias_text="sleep stack",
            ),
            AssistantMemoryRecord(
                id="memory-1",
                kind="entity_alias",
                entity_id="other-1",
                alias_text="alias one",
            ),
            AssistantMemoryRecord(
                id="memory-2",
                kind="entity_alias",
                entity_id="other-2",
                alias_text="alias two",
            ),
            AssistantMemoryRecord(
                id="memory-3",
                kind="entity_alias",
                entity_id="other-3",
                alias_text="alias three",
            ),
            AssistantMemoryRecord(
                id="memory-4",
                kind="entity_alias",
                entity_id="other-4",
                alias_text="alias four",
            ),
            AssistantMemoryRecord(
                id="memory-5",
                kind="entity_alias",
                entity_id="other-5",
                alias_text="alias five",
            ),
        ],
    )
    runtime = _FakeRuntime(deltas=["I found the right experiment."])

    lines = asyncio.run(
        _collect(
            stream_reply(
                repo=cast(Any, repo),
                read_store=_FakeReadStore.for_experiment_review(),
                runtime=cast(Any, runtime),
                thread_id="thread-1",
                request=AssistantMessageCreateRequest(
                    id="message-7",
                    content="sleep stack",
                ),
            )
        )
    )

    payloads = [json.loads(line) for line in lines]
    assert payloads[-1]["type"] == "done"
    evidence_bundle = runtime.stream_chat_kwargs[0]["evidence_bundle"]
    assert isinstance(evidence_bundle, AssistantEvidenceBundle)
    assert evidence_bundle.intent == "experiment_review"
    prompt_memory_records = runtime.stream_chat_kwargs[0]["memory_records"]
    assert isinstance(prompt_memory_records, list)
    assert all(
        not (
            isinstance(memory_record, AssistantMemoryRecord)
            and memory_record.alias_text == "sleep stack"
        )
        for memory_record in prompt_memory_records
    )
    assert any(
        call["kind"] == "entity_alias"
        and isinstance(call["alias_candidates"], tuple)
        and "sleep stack" in call["alias_candidates"]
        for call in repo.list_memory_calls
    )


def test_stream_reply_alias_reroute_handles_natural_language_follow_up():
    repo = _FakeConversationStore.with_thread(
        thread_id="thread-1",
        memory_records=[
            AssistantMemoryRecord(
                id="memory-3",
                kind="entity_alias",
                entity_id="meditation-hrv-2026-03",
                alias_text="sleep stack",
            )
        ],
    )
    runtime = _FakeRuntime(deltas=["The experiment is still trending cleanly."])

    lines = asyncio.run(
        _collect(
            stream_reply(
                repo=cast(Any, repo),
                read_store=_FakeReadStore.for_experiment_review(),
                runtime=cast(Any, runtime),
                thread_id="thread-1",
                request=AssistantMessageCreateRequest(
                    id="message-9",
                    content="How is sleep stack going?",
                ),
            )
        )
    )

    payloads = [json.loads(line) for line in lines]
    assert payloads[-1]["type"] == "done"
    evidence_bundle = runtime.stream_chat_kwargs[0]["evidence_bundle"]
    assert isinstance(evidence_bundle, AssistantEvidenceBundle)
    assert evidence_bundle.intent == "experiment_review"
    assert any(entity.entity_id == "meditation-hrv-2026-03" for entity in evidence_bundle.entities)


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


def test_stream_reply_memory_setup_failure_emits_error_without_run():
    """Memory loading fails before the run is created — error emitted, no run persisted."""
    repo = _FakeConversationStore.with_thread(
        thread_id="thread-1",
        fail_on_list_memory_records=True,
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
                    id="message-8",
                    content="How does our meditation experiment look like so far?",
                ),
            )
        )
    )

    payloads = [json.loads(line) for line in lines]
    assert payloads[-1]["type"] == "error"
    assert "run_id" not in payloads[-1]
    assert repo.saved_runs == []
    assert runtime.stream_chat_kwargs == []


def test_stream_reply_final_persistence_failure_emits_error_and_marks_run_failed():
    repo = _FakeConversationStore.with_thread(
        thread_id="thread-1",
        fail_on_finalize_reply=True,
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
                    content="Meditation to HRV",
                ),
            )
        )
    )

    payloads = [json.loads(line) for line in lines]
    assert payloads[-1]["type"] == "error"
    assert payloads[-1]["run_id"].startswith("run-")
    assert repo.saved_runs[-1].status == "failed"
    assert repo.saved_memory_records == []
    assert not any(getattr(message, "role", "") == "assistant" for message in repo.messages)
    assert not any(run.status == "completed" for run in repo.saved_runs)
