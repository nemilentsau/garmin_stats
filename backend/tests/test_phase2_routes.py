"""Tests for assistant routes."""

import asyncio

import pytest
from fastapi import HTTPException

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

    def test_get_thread_detail_returns_404_when_missing(self, monkeypatch):
        monkeypatch.setattr(
            assistant_router_mod,
            "get_thread",
            lambda *_args: (_ for _ in ()).throw(LookupError("Assistant thread missing")),
        )

        with pytest.raises(HTTPException, match="Assistant thread missing"):
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

    def test_post_thread_message_returns_404_when_thread_missing(self, monkeypatch):
        monkeypatch.setattr(
            assistant_router_mod,
            "get_thread",
            lambda *_args: (_ for _ in ()).throw(LookupError("Assistant thread missing")),
        )

        with pytest.raises(HTTPException, match="Assistant thread missing"):
            asyncio.run(
                assistant_router_mod.post_thread_message(
                    "thread-1",
                    AssistantMessageCreateRequest(id="message-1", content="Hi"),
                )
            )

    def test_get_thread_messages_returns_404_when_missing(self, monkeypatch):
        monkeypatch.setattr(
            assistant_router_mod,
            "list_messages",
            lambda *_args: (_ for _ in ()).throw(LookupError("Assistant thread missing")),
        )

        with pytest.raises(HTTPException, match="Assistant thread missing"):
            assistant_router_mod.get_thread_messages("thread-1")
