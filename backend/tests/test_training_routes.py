"""Tests for training-runtime route error handling."""

import asyncio
import json

import pytest
from fastapi import FastAPI
from starlette.types import Message

import app.routers.assistant_artifact_bundles as artifact_bundles_mod
import app.routers.assistant_artifacts as artifacts_mod
import app.routers.today as today_mod
from app.models import CardLogRangeResponse, CardLogStatusEntry


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


async def _artifact_bundle_status(path: str, body: dict[str, object]) -> int:
    app = FastAPI()
    app.include_router(artifact_bundles_mod.router)

    messages: list[Message] = []
    payload = json.dumps(body).encode()
    receive_calls = 0

    async def receive() -> Message:
        nonlocal receive_calls
        receive_calls += 1
        if receive_calls == 1:
            return {"type": "http.request", "body": payload, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        messages.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": [(b"content-type", b"application/json")],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        },
        receive,
        send,
    )

    start = next(message for message in messages if message["type"] == "http.response.start")
    return int(start["status"])  # type: ignore[arg-type]


class TestAssistantArtifactRoutes:
    def test_activate_artifact_raises_value_error_when_rejected(self, monkeypatch):
        monkeypatch.setattr(
            artifacts_mod,
            "activate_assistant_artifact",
            lambda *_args: (_ for _ in ()).throw(ValueError("Artifact is not ready")),
        )

        with pytest.raises(ValueError, match="Artifact is not ready"):
            artifacts_mod.post_activate_artifact("artifact-1")


class TestAssistantArtifactBundleRoutes:
    def test_import_bundle_raises_value_error_when_service_rejects_it(self, monkeypatch):
        monkeypatch.setattr(
            artifact_bundles_mod,
            "import_artifact_bundle",
            lambda *_args: (_ for _ in ()).throw(ValueError("Bundle has blocking issues")),
        )

        with pytest.raises(ValueError, match="Bundle has blocking issues"):
            artifact_bundles_mod.post_import_bundle(
                artifact_bundles_mod.ArtifactBundleSpec(
                    id="bundle",
                    name="Bundle",
                    card_templates=[],
                    routine_specs=[],
                )
            )

    def test_preview_bundle_returns_422_for_malformed_payload(self):
        status = asyncio.run(
            _artifact_bundle_status("/api/assistant/artifact-bundles/preview", {"id": "bundle"})
        )

        assert status == 422


class TestTodayRoutes:
    def test_get_card_logs_range_delegates_through_today_service(self, monkeypatch):
        def _service_response(*_args, **_kwargs):
            return CardLogRangeResponse(
                start_date="2026-03-02",
                end_date="2026-03-03",
                entries=[
                    CardLogStatusEntry(
                        occurrence_key="scheduled:assignment-1:2026-03-02",
                        status="completed",
                    )
                ],
            )

        def _db_leak(*_args, **_kwargs):
            raise AssertionError("Route should delegate through app.services.today")

        monkeypatch.setattr(today_mod, "get_card_log_range", _service_response, raising=False)
        monkeypatch.setattr(today_mod, "load_card_logs_range", _db_leak, raising=False)

        response = today_mod.get_card_logs_range("2026-03-02", "2026-03-03")

        assert response.start_date == "2026-03-02"
        assert response.end_date == "2026-03-03"
        assert response.entries == [
            CardLogStatusEntry(
                occurrence_key="scheduled:assignment-1:2026-03-02",
                status="completed",
            )
        ]

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
