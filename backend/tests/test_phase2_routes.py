"""Tests for assistant routes."""

import asyncio
import json

import pytest

import app.routers.assistant as assistant_router_mod
from app.models import (
    AssistantMessageCreateRequest,
    AssistantThread,
    AssistantThreadCreateRequest,
    AssistantThreadsResponse,
)


class TestAssistantRoutes:
    def test_get_threads_returns_service_response(self, monkeypatch):
        monkeypatch.setattr(
            assistant_router_mod,
            "list_threads",
            lambda: AssistantThreadsResponse(
                threads=[AssistantThread(id="thread-1", title="Recovery")],
                total=1,
            ),
        )

        response = assistant_router_mod.get_threads()

        assert response.total == 1

    def test_get_thread_detail_raises_lookup_error_when_missing(self, monkeypatch):
        monkeypatch.setattr(
            assistant_router_mod,
            "get_thread",
            lambda *_args: (_ for _ in ()).throw(LookupError("Assistant thread missing")),
        )

        with pytest.raises(LookupError, match="Assistant thread missing"):
            assistant_router_mod.get_thread_detail("thread-1")

    def test_post_thread_creates_thread(self, monkeypatch):
        monkeypatch.setattr(
            assistant_router_mod,
            "create_thread",
            lambda request: AssistantThread(id=request.id, title=request.title),
        )

        response = assistant_router_mod.post_thread(
            AssistantThreadCreateRequest(id="thread-1", title="Recovery")
        )

        assert response.id == "thread-1"

    def test_post_thread_message_returns_ndjson_stream(self, monkeypatch):
        async def fake_stream(*_args, **_kwargs):
            yield '{"type":"done"}\n'

        monkeypatch.setattr(
            assistant_router_mod,
            "get_thread",
            lambda thread_id: AssistantThread(id=thread_id, title="Recovery"),
        )
        monkeypatch.setattr(assistant_router_mod, "stream_thread_reply", fake_stream)

        response = asyncio.run(
            assistant_router_mod.post_thread_message(
                "thread-1",
                AssistantMessageCreateRequest(id="message-1", content="Hi"),
            )
        )

        assert response.media_type == "application/x-ndjson"

    def test_post_thread_message_keeps_ndjson_contract(self, monkeypatch):
        async def fake_stream_reply(*_args, **_kwargs):
            yield '{"type": "delta", "text": "hello"}\n'
            yield '{"type": "done", "message": {"id": "assistant-1", "thread_id": "thread-1", "role": "assistant", "content_markdown": "hello"}, "session_id": None, "snapshot_id": "evidence-1", "run_id": "run-1"}\n'

        async def legacy_stream_used(*_args, **_kwargs):
            if False:
                yield ""
            raise AssertionError("legacy stream owner is still used by the route")

        monkeypatch.setattr(
            assistant_router_mod,
            "get_thread",
            lambda thread_id: AssistantThread(id=thread_id, title="Recovery"),
        )
        monkeypatch.setattr(assistant_router_mod, "stream_thread_reply", legacy_stream_used)
        monkeypatch.setattr(
            assistant_router_mod,
            "stream_reply",
            fake_stream_reply,
            raising=False,
        )

        response = asyncio.run(
            assistant_router_mod.post_thread_message(
                "thread-1",
                AssistantMessageCreateRequest(id="message-1", content="Hi"),
            )
        )

        async def collect_lines(stream):
            lines = []
            async for line in stream:
                if isinstance(line, (bytes, bytearray)):
                    line = line.decode()
                lines.append(line)
            return lines

        payloads = [
            json.loads(line) for line in asyncio.run(collect_lines(response.body_iterator))
        ]

        assert response.media_type == "application/x-ndjson"
        assert payloads[0] == {"type": "delta", "text": "hello"}
        assert payloads[-1]["type"] == "done"
        assert payloads[-1]["message"]["id"] == "assistant-1"
        assert payloads[-1]["message"]["thread_id"] == "thread-1"
        assert payloads[-1]["message"]["role"] == "assistant"
        assert payloads[-1]["message"]["content_markdown"] == "hello"

    def test_post_thread_message_raises_lookup_error_when_thread_missing(self, monkeypatch):
        monkeypatch.setattr(
            assistant_router_mod,
            "get_thread",
            lambda *_args: (_ for _ in ()).throw(LookupError("Assistant thread missing")),
        )

        with pytest.raises(LookupError, match="Assistant thread missing"):
            asyncio.run(
                assistant_router_mod.post_thread_message(
                    "thread-1",
                    AssistantMessageCreateRequest(id="message-1", content="Hi"),
                )
            )

    def test_get_thread_messages_raises_lookup_error_when_missing(self, monkeypatch):
        monkeypatch.setattr(
            assistant_router_mod,
            "list_messages",
            lambda *_args: (_ for _ in ()).throw(LookupError("Assistant thread missing")),
        )

        with pytest.raises(LookupError, match="Assistant thread missing"):
            assistant_router_mod.get_thread_messages("thread-1")
