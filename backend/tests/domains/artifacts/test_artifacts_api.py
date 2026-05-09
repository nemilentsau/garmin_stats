"""Tests for artifact route error handling."""

import asyncio
import json

import pytest
from fastapi import FastAPI
from starlette.types import Message

import app.domains.artifacts.routes as artifacts_mod


async def _artifact_bundle_status(path: str, body: dict[str, object]) -> int:
    app = FastAPI()
    app.include_router(artifacts_mod.assistant_artifact_bundles_router)

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
            artifacts_mod,
            "import_artifact_bundle",
            lambda *_args: (_ for _ in ()).throw(ValueError("Bundle has blocking issues")),
        )

        with pytest.raises(ValueError, match="Bundle has blocking issues"):
            artifacts_mod.post_import_bundle(
                artifacts_mod.ArtifactBundleSpec(
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
