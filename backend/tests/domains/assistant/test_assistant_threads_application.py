"""Tests for assistant thread and message catalog use cases."""

import pytest

from app.domains.assistant.application.threads import create_thread, list_messages, list_threads
from app.domains.assistant.contracts import (
    AssistantEvidenceBundle,
    AssistantMemoryRecord,
    AssistantMessage,
    AssistantMessagesResponse,
    AssistantRun,
    AssistantThread,
    AssistantThreadCreateRequest,
    AssistantThreadsResponse,
)


class _FakeConversationStore:
    def __init__(
        self,
        *,
        threads: list[AssistantThread] | None = None,
        messages: list[AssistantMessage] | None = None,
    ) -> None:
        self._threads = {thread.id: thread for thread in threads or []}
        self._messages = list(messages or [])

    def list_threads(self) -> list[AssistantThread]:
        return list(self._threads.values())

    def get_thread(self, thread_id: str) -> AssistantThread | None:
        return self._threads.get(thread_id)

    def list_messages(self, thread_id: str) -> list[AssistantMessage]:
        return [message for message in self._messages if message.thread_id == thread_id]

    def create_thread(self, thread: AssistantThread) -> None:
        if thread.id in self._threads:
            raise ValueError(f"Assistant thread {thread.id} already exists")
        self._threads[thread.id] = thread

    def save_thread(self, thread: AssistantThread) -> None:
        self._threads[thread.id] = thread

    def save_message(self, message: AssistantMessage) -> None:
        self._messages.append(message)

    def save_run(self, run: AssistantRun) -> None:
        _ = run

    def finalize_reply(
        self,
        *,
        assistant_message: AssistantMessage,
        updated_thread: AssistantThread,
        completed_run: AssistantRun,
        memory_record: AssistantMemoryRecord | None = None,
    ) -> None:
        self._messages.append(assistant_message)
        self._threads[updated_thread.id] = updated_thread
        _ = completed_run
        _ = memory_record

    def save_evidence_bundle(self, bundle: AssistantEvidenceBundle) -> None:
        _ = bundle

    def list_evidence_bundles(
        self,
        thread_id: str | None = None,
        *,
        last_n: int | None = None,
    ) -> list[AssistantEvidenceBundle]:
        _ = (thread_id, last_n)
        return []

    def save_memory_record(self, record: AssistantMemoryRecord) -> None:
        _ = record

    def list_memory_records(
        self,
        kind: str | None = None,
        *,
        last_n: int | None = None,
        alias_candidates: tuple[str, ...] | None = None,
    ) -> list[AssistantMemoryRecord]:
        _ = (kind, last_n, alias_candidates)
        return []


def test_list_threads_orders_by_last_message_desc() -> None:
    repo = _FakeConversationStore(
        threads=[
            AssistantThread(
                id="older",
                title="Older",
                last_message_at="2026-04-10T10:00:00+00:00",
            ),
            AssistantThread(
                id="newer",
                title="Newer",
                last_message_at="2026-04-11T10:00:00+00:00",
            ),
        ]
    )

    response = list_threads(repo)

    assert isinstance(response, AssistantThreadsResponse)
    assert [thread.id for thread in response.threads] == ["newer", "older"]


def test_list_messages_raises_for_missing_thread() -> None:
    repo = _FakeConversationStore(threads=[], messages=[])

    with pytest.raises(LookupError, match="Assistant thread missing not found"):
        list_messages(repo, "missing")


def test_list_messages_returns_messages_for_existing_thread() -> None:
    repo = _FakeConversationStore(
        threads=[AssistantThread(id="thread-1", title="Recovery")],
        messages=[
            AssistantMessage(
                id="message-1",
                thread_id="thread-1",
                role="user",
                content_markdown="How am I doing?",
            )
        ],
    )

    response = list_messages(repo, "thread-1")

    assert isinstance(response, AssistantMessagesResponse)
    assert [message.id for message in response.messages] == ["message-1"]


def test_create_thread_rejects_duplicate_id() -> None:
    repo = _FakeConversationStore(
        threads=[AssistantThread(id="thread-1", title="Original", mode="general", model="sonnet")]
    )

    with pytest.raises(ValueError, match="Assistant thread thread-1 already exists"):
        create_thread(
            repo,
            AssistantThreadCreateRequest(
                id="thread-1",
                title="Replacement",
                mode="analysis",
                model="opus",
            ),
        )

    thread = repo.get_thread("thread-1")
    assert thread is not None
    assert thread.title == "Original"
