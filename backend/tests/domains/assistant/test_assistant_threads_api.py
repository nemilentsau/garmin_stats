"""Tests for assistant routes."""

import asyncio
import importlib
import json
import sys
from types import SimpleNamespace

import pytest

from app.domains.assistant.contracts import (
    AssistantMessageCreateRequest,
    AssistantThread,
    AssistantThreadCreateRequest,
    AssistantThreadsResponse,
)


def _load_assistant_router():
    if "app.domains.assistant.api.threads" in sys.modules:
        del sys.modules["app.domains.assistant.api.threads"]
    importlib.invalidate_caches()
    return importlib.import_module("app.domains.assistant.api.threads")


def _patch_container(monkeypatch, assistant_router_mod):
    repo = object()
    runtime = object()
    monkeypatch.setattr(
        assistant_router_mod,
        "build_container",
        lambda: SimpleNamespace(assistant_repo=repo, assistant_runtime=runtime),
    )
    return repo, runtime


class TestAssistantRoutes:
    def test_get_threads_returns_service_response(self, monkeypatch):
        assistant_router_mod = _load_assistant_router()
        repo, _runtime = _patch_container(monkeypatch, assistant_router_mod)

        monkeypatch.setattr(
            assistant_router_mod,
            "list_threads",
            lambda candidate_repo: (
                AssistantThreadsResponse(
                    threads=[AssistantThread(id="thread-1", title="Recovery")],
                    total=1,
                )
                if candidate_repo is repo
                else (_ for _ in ()).throw(AssertionError("unexpected repository"))
            ),
        )

        response = assistant_router_mod.get_threads()

        assert response.total == 1

    def test_get_thread_detail_raises_lookup_error_when_missing(self, monkeypatch):
        assistant_router_mod = _load_assistant_router()
        repo, _runtime = _patch_container(monkeypatch, assistant_router_mod)

        monkeypatch.setattr(
            assistant_router_mod,
            "get_thread",
            lambda candidate_repo, *_args: (
                (_ for _ in ()).throw(LookupError("Assistant thread missing"))
                if candidate_repo is repo
                else (_ for _ in ()).throw(AssertionError("unexpected repository"))
            ),
        )

        with pytest.raises(LookupError, match="Assistant thread missing"):
            assistant_router_mod.get_thread_detail("thread-1")

    def test_post_thread_creates_thread(self, monkeypatch):
        assistant_router_mod = _load_assistant_router()
        repo, _runtime = _patch_container(monkeypatch, assistant_router_mod)

        monkeypatch.setattr(
            assistant_router_mod,
            "create_thread",
            lambda candidate_repo, request: (
                AssistantThread(id=request.id, title=request.title)
                if candidate_repo is repo
                else (_ for _ in ()).throw(AssertionError("unexpected repository"))
            ),
        )

        response = assistant_router_mod.post_thread(
            AssistantThreadCreateRequest(id="thread-1", title="Recovery")
        )

        assert response.id == "thread-1"

    def test_post_thread_message_returns_ndjson_stream(self, monkeypatch):
        assistant_router_mod = _load_assistant_router()
        _repo, runtime = _patch_container(monkeypatch, assistant_router_mod)

        async def fake_stream_reply(*_args, **_kwargs):
            assert _kwargs["runtime"] is runtime
            yield '{"type":"done"}\n'

        monkeypatch.setattr(
            assistant_router_mod,
            "get_thread",
            lambda *_args: AssistantThread(id="thread-1", title="Recovery"),
        )
        monkeypatch.setattr(assistant_router_mod, "stream_reply", fake_stream_reply)

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
        assistant_router_mod = _load_assistant_router()
        _repo, runtime = _patch_container(monkeypatch, assistant_router_mod)

        async def fake_stream_reply(*_args, **_kwargs):
            assert _kwargs["runtime"] is runtime
            yield '{"type": "delta", "text": "hello"}\n'
            yield (
                '{"type": "done", "message": {"id": "assistant-1", '
                '"thread_id": "thread-1", "role": "assistant", '
                '"content_markdown": "hello"}, "session_id": null, '
                '"snapshot_id": "evidence-1", "run_id": "run-1"}\n'
            )

        monkeypatch.setattr(
            assistant_router_mod,
            "get_thread",
            lambda *_args: AssistantThread(id="thread-1", title="Recovery"),
        )
        monkeypatch.setattr(assistant_router_mod, "stream_reply", fake_stream_reply)

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
        assistant_router_mod = _load_assistant_router()
        repo, _runtime = _patch_container(monkeypatch, assistant_router_mod)

        monkeypatch.setattr(
            assistant_router_mod,
            "get_thread",
            lambda candidate_repo, *_args: (
                (_ for _ in ()).throw(LookupError("Assistant thread missing"))
                if candidate_repo is repo
                else (_ for _ in ()).throw(AssertionError("unexpected repository"))
            ),
        )

        with pytest.raises(LookupError, match="Assistant thread missing"):
            asyncio.run(
                assistant_router_mod.post_thread_message(
                    "thread-1",
                    AssistantMessageCreateRequest(id="message-1", content="Hi"),
                )
            )

    def test_get_thread_messages_raises_lookup_error_when_missing(self, monkeypatch):
        assistant_router_mod = _load_assistant_router()
        repo, _runtime = _patch_container(monkeypatch, assistant_router_mod)

        monkeypatch.setattr(
            assistant_router_mod,
            "list_messages",
            lambda candidate_repo, *_args: (
                (_ for _ in ()).throw(LookupError("Assistant thread missing"))
                if candidate_repo is repo
                else (_ for _ in ()).throw(AssertionError("unexpected repository"))
            ),
        )

        with pytest.raises(LookupError, match="Assistant thread missing"):
            assistant_router_mod.get_thread_messages("thread-1")
