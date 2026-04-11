"""Tests for assistant service streaming."""

import asyncio
import json
from types import SimpleNamespace

import app.services.assistant as assistant_mod
from app.models import (
    AssistantMessageCreateRequest,
    AssistantThread,
    ContextSnapshot,
)


class _SuccessRuntime:
    async def stream_chat(self, **_kwargs):
        yield {"type": "delta", "text": "Focus on "}
        yield {"type": "delta", "text": "sleep tonight."}
        yield {"type": "done", "session_id": "session-123"}


class _FailingRuntime:
    async def stream_chat(self, **_kwargs):
        if False:
            yield {"type": "delta", "text": ""}
        raise RuntimeError("claude failed")


async def _collect(stream):
    lines = []
    async for line in stream:
        lines.append(line)
    return lines


def _patch_assistant_repo(monkeypatch, thread_id: str = "thread-1") -> None:
    class _Repo:
        def get_thread(self, candidate_thread_id: str) -> AssistantThread | None:
            if candidate_thread_id != thread_id:
                return None
            return AssistantThread(id=candidate_thread_id, title="Recovery")

    monkeypatch.setattr(
        assistant_mod,
        "build_container",
        lambda: SimpleNamespace(assistant_repo=_Repo()),
    )


class TestStreamThreadReply:
    def test_persists_assistant_reply_and_completes_run(self, monkeypatch):
        saved_messages = []
        saved_runs = []
        saved_threads = []
        broadcast_events = []

        _patch_assistant_repo(monkeypatch)
        monkeypatch.setattr(assistant_mod, "save_assistant_message", saved_messages.append)
        monkeypatch.setattr(assistant_mod, "save_assistant_run", saved_runs.append)
        monkeypatch.setattr(assistant_mod, "save_assistant_thread", saved_threads.append)
        monkeypatch.setattr(
            assistant_mod,
            "build_context_snapshot",
            lambda: ContextSnapshot(id="snapshot-1", snapshot_json={"recent_daily_metrics": []}),
        )
        monkeypatch.setattr(assistant_mod, "_runtime", _SuccessRuntime())

        async def fake_broadcast(event: str, data: str = "") -> None:
            broadcast_events.append((event, json.loads(data) if data else None))

        monkeypatch.setattr(assistant_mod.event_bus, "broadcast", fake_broadcast)

        lines = asyncio.run(
            _collect(
                assistant_mod.stream_thread_reply(
                    "thread-1",
                    AssistantMessageCreateRequest(id="message-1", content="How am I doing?"),
                )
            )
        )

        delta_payload = json.loads(lines[0])
        done_payload = json.loads(lines[-1])

        assert delta_payload == {"type": "delta", "text": "Focus on "}
        assert done_payload["type"] == "done"
        assert done_payload["session_id"] == "session-123"
        assert saved_messages[0].role == "user"
        assert saved_messages[1].role == "assistant"
        assert saved_messages[1].content_markdown == "Focus on sleep tonight."
        assert saved_threads[0].last_message_at == saved_messages[0].created_at
        assert saved_runs[-1].status == "completed"
        assert saved_threads[-1].claude_session_id == "session-123"
        assert [event for event, _data in broadcast_events] == [
            "assistant_run_started",
            "assistant_stream_delta",
            "assistant_stream_delta",
            "assistant_run_completed",
        ]

    def test_marks_run_failed_when_runtime_raises(self, monkeypatch):
        saved_messages = []
        saved_runs = []
        broadcast_events = []

        _patch_assistant_repo(monkeypatch)
        monkeypatch.setattr(assistant_mod, "save_assistant_message", saved_messages.append)
        monkeypatch.setattr(assistant_mod, "save_assistant_run", saved_runs.append)
        monkeypatch.setattr(assistant_mod, "save_assistant_thread", lambda _thread: None)
        monkeypatch.setattr(
            assistant_mod,
            "build_context_snapshot",
            lambda: ContextSnapshot(id="snapshot-1", snapshot_json={}),
        )
        monkeypatch.setattr(assistant_mod, "_runtime", _FailingRuntime())

        async def fake_broadcast(event: str, data: str = "") -> None:
            broadcast_events.append((event, json.loads(data) if data else None))

        monkeypatch.setattr(assistant_mod.event_bus, "broadcast", fake_broadcast)

        lines = asyncio.run(
            _collect(
                assistant_mod.stream_thread_reply(
                    "thread-1",
                    AssistantMessageCreateRequest(id="message-1", content="Need a recap"),
                )
            )
        )

        error_payload = json.loads(lines[-1])

        assert error_payload["type"] == "error"
        assert len(saved_messages) == 1
        assert saved_messages[0].role == "user"
        assert saved_runs[-1].status == "failed"
        assert [event for event, _data in broadcast_events] == [
            "assistant_run_started",
            "assistant_run_failed",
        ]

    def test_marks_run_failed_when_setup_raises(self, monkeypatch):
        saved_messages = []
        saved_runs = []
        saved_threads = []
        broadcast_events = []

        _patch_assistant_repo(monkeypatch)
        monkeypatch.setattr(assistant_mod, "save_assistant_message", saved_messages.append)
        monkeypatch.setattr(assistant_mod, "save_assistant_run", saved_runs.append)
        monkeypatch.setattr(assistant_mod, "save_assistant_thread", saved_threads.append)
        monkeypatch.setattr(
            assistant_mod,
            "build_context_snapshot",
            lambda: (_ for _ in ()).throw(RuntimeError("snapshot failed")),
        )

        async def fake_broadcast(event: str, data: str = "") -> None:
            broadcast_events.append((event, json.loads(data) if data else None))

        monkeypatch.setattr(assistant_mod.event_bus, "broadcast", fake_broadcast)

        lines = asyncio.run(
            _collect(
                assistant_mod.stream_thread_reply(
                    "thread-1",
                    AssistantMessageCreateRequest(id="message-1", content="Need a recap"),
                )
            )
        )

        error_payload = json.loads(lines[-1])

        assert error_payload["type"] == "error"
        assert error_payload["run_id"].startswith("run-")
        assert saved_messages[0].role == "user"
        assert saved_threads[0].last_message_at == saved_messages[0].created_at
        assert saved_runs[-1].status == "failed"
        assert [event for event, _data in broadcast_events] == ["assistant_run_failed"]
