"""Tests for assistant routes."""

import asyncio
import json
import sys
import types

import pytest

import app.routers.assistant as assistant_router_mod
from app.models import (
    AssistantMessageCreateRequest,
    AssistantThread,
    AssistantThreadCreateRequest,
    AssistantThreadsResponse,
)


def _install_future_chat_owner(monkeypatch, stream_reply):
    application_module = types.ModuleType("app.domains.assistant.application")
    chat_module = types.ModuleType("app.domains.assistant.application.chat")
    chat_module.stream_reply = stream_reply
    application_module.chat = chat_module

    assistant_module = types.ModuleType("app.domains.assistant")
    assistant_module.application = application_module

    domains_module = types.ModuleType("app.domains")
    domains_module.assistant = assistant_module

    for module_name, module in {
        "app.domains": domains_module,
        "app.domains.assistant": assistant_module,
        "app.domains.assistant.application": application_module,
        "app.domains.assistant.application.chat": chat_module,
    }.items():
        monkeypatch.setitem(sys.modules, module_name, module)

    application_module.__path__ = []  # type: ignore[attr-defined]
    assistant_module.__path__ = []  # type: ignore[attr-defined]
    domains_module.__path__ = []  # type: ignore[attr-defined]


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
        async def fake_stream_reply(*_args, **_kwargs):
            yield '{"type":"done"}\n'

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
        _install_future_chat_owner(monkeypatch, fake_stream_reply)

        response = asyncio.run(
            assistant_router_mod.post_thread_message(
                "thread-1",
                AssistantMessageCreateRequest(id="message-1", content="Hi"),
            )
        )

        async def collect_first_line(stream):
            async for line in stream:
                if isinstance(line, (bytes, bytearray)):
                    line = line.decode()
                return line
            return ""

        first_line = asyncio.run(collect_first_line(response.body_iterator))
        payload = json.loads(first_line)

        assert response.media_type == "application/x-ndjson"
        assert payload == {"type": "done"}

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
        _install_future_chat_owner(monkeypatch, fake_stream_reply)

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
        assert payloads[-1]["session_id"] is None
        assert payloads[-1]["snapshot_id"] == "evidence-1"
        assert payloads[-1]["run_id"] == "run-1"

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
