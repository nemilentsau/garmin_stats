"""Tests for assistant chat application orchestration."""

import asyncio
import json
import importlib
from collections.abc import AsyncIterator

from app.models import AssistantMessageCreateRequest


async def _legacy_stream_reply(
    repo,
    read_store,
    runtime,
    thread_id: str,
    request: AssistantMessageCreateRequest,
) -> AsyncIterator[str]:
    thread = repo.get_thread(thread_id)
    prior_messages = repo.list_messages(thread_id)
    session_id = thread["claude_session_id"] if thread else None

    async for event in runtime.stream_chat(
        user_message=request.content,
        prior_messages=prior_messages,
        session_id=session_id,
        resume=bool(session_id),
    ):
        yield json.dumps(event) + "\n"


def _load_stream_reply():
    try:
        return importlib.import_module(
            "app.domains.assistant.application.chat"
        ).stream_reply
    except ModuleNotFoundError:
        return _legacy_stream_reply


async def _collect(stream):
    events = []
    async for event in stream:
        events.append(event)
    return events


class _FakeRuntime:
    def __init__(self, deltas: list[str]):
        self._deltas = list(deltas)
        self.stream_chat_kwargs: list[dict[str, object]] = []

    async def stream_chat(self, **_kwargs):
        self.stream_chat_kwargs.append(dict(_kwargs))
        for delta in self._deltas:
            yield {"type": "delta", "text": delta}
        yield {
            "type": "done",
            "message": {
                "id": "assistant-1",
                "thread_id": "thread-1",
                "role": "assistant",
                "content_markdown": "".join(self._deltas),
            },
            "session_id": None,
            "snapshot_id": "evidence-1",
            "run_id": "run-1",
        }


class _FakeConversationStore:
    def __init__(self, thread_id: str, claude_session_id: str | None):
        self.thread_id = thread_id
        self.claude_session_id = claude_session_id
        self.messages: list[object] = []
        self.evidence_bundles: list[object] = []

    @classmethod
    def with_thread(
        cls,
        thread_id: str,
        claude_session_id: str | None = None,
        prior_messages: list[object] | None = None,
    ):
        thread = cls(thread_id=thread_id, claude_session_id=claude_session_id)
        thread.messages = list(prior_messages or [])
        return thread

    def get_thread(self, thread_id: str):
        if thread_id != self.thread_id:
            return None
        return {"id": thread_id, "claude_session_id": self.claude_session_id}

    def list_messages(self, thread_id: str):
        if thread_id != self.thread_id:
            return []
        return list(self.messages)

    def save_message(self, message):
        self.messages.append(message)

    def save_evidence_bundle(self, bundle):
        self.evidence_bundles.append(bundle)


class _FakeReadStore:
    @classmethod
    def for_experiment_review(cls):
        return cls()


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
    stream_reply = _load_stream_reply()

    lines = asyncio.run(
        _collect(
            stream_reply(
                repo=repo,
                read_store=_FakeReadStore.for_experiment_review(),
                runtime=runtime,
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
    assert [
        (message["id"], message["role"], message["content_markdown"])
        for message in runtime.stream_chat_kwargs[0]["prior_messages"]
    ] == [
        (message["id"], message["role"], message["content_markdown"])
        for message in seeded_prior_messages
    ]
    assert "claude_session_id" not in runtime.stream_chat_kwargs[0]
    assert "session_id" not in runtime.stream_chat_kwargs[0]
    assert not any(
        "resume" in str(key).lower()
        for key in runtime.stream_chat_kwargs[0]
    )
