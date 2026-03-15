"""Tests for training-runtime route error handling."""

import pytest
from fastapi import HTTPException

import app.routers.assistant_artifacts as artifacts_mod
import app.routers.today as today_mod
from app.models import TodayCardOverrideCreateRequest


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
    def test_post_today_override_returns_404_when_card_template_missing(self, monkeypatch):
        monkeypatch.setattr(
            today_mod,
            "create_today_override",
            lambda *_args: (_ for _ in ()).throw(LookupError("Card template missing")),
        )

        with pytest.raises(HTTPException, match="Card template missing"):
            today_mod.post_today_override(
                "2026-03-02",
                TodayCardOverrideCreateRequest(
                    id="override-1",
                    action="add",
                    card_template_id="card-missing",
                    slot="morning",
                    position=5,
                ),
            )
