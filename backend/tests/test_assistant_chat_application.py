"""Tests for assistant chat application orchestration."""

import json
import importlib
import asyncio

from app.models import AssistantMessageCreateRequest


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
    def with_thread(cls, thread_id: str, claude_session_id: str | None = None):
        return cls(thread_id=thread_id, claude_session_id=claude_session_id)

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
    repo = _FakeConversationStore.with_thread(
        thread_id="thread-1",
        claude_session_id="stale-session-id",
    )
    runtime = _FakeRuntime(deltas=["You should keep going."])
    stream_reply = importlib.import_module(
        "app.domains.assistant.application.chat"
    ).stream_reply

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
    assert "claude_session_id" not in runtime.stream_chat_kwargs[0]
    assert "session_id" not in runtime.stream_chat_kwargs[0]
    assert not any(
        "resume" in str(key).lower()
        for key in runtime.stream_chat_kwargs[0]
    )
