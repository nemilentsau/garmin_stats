"""Tests for training-runtime route error handling."""

import asyncio

import pytest
from fastapi import FastAPI, HTTPException
from starlette.types import Message

import app.routers.assistant_artifacts as artifacts_mod
import app.routers.today as today_mod


async def _today_status(method: str, path: str) -> int:
    app = FastAPI()
    app.include_router(today_mod.router)

    messages: list[Message] = []

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        messages.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        },
        receive,
        send,
    )

    start = next(message for message in messages if message["type"] == "http.response.start")
    return int(start["status"])  # type: ignore[arg-type]


class TestAssistantArtifactRoutes:
    def test_activate_artifact_returns_400_when_service_rejects_activation(self, monkeypatch):
        monkeypatch.setattr(
            artifacts_mod,
            "activate_assistant_artifact",
            lambda *_args: (_ for _ in ()).throw(ValueError("Artifact is not ready")),
        )

        with pytest.raises(HTTPException, match="Artifact is not ready"):
            artifacts_mod.post_activate_artifact("artifact-1")


class TestTodayRoutes:
    def test_post_today_cards_returns_404(self):
        status = asyncio.run(_today_status("POST", "/api/today/2026-03-02/cards"))

        assert status == 404

    def test_delete_today_card_returns_405(self):
        status = asyncio.run(
            _today_status(
                "DELETE",
                "/api/today/2026-03-02/cards/scheduled:assignment-1:2026-03-02",
            )
        )

        assert status == 405
