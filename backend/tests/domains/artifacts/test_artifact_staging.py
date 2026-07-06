"""Tests for artifact staging: capability-request auto-creation.

Staging a card_template draft whose payload requests a card type outside the
CardPayload union must record a capability_request artifact so repeated demand
for new card types leaves a queryable product signal. Supported-but-invalid and
fully valid drafts must not create one.
"""

from __future__ import annotations

from app.domains.artifacts.adapters import SqliteArtifactRepository
from app.domains.artifacts.contracts import AssistantArtifactCreateRequest
from tests._artifacts_helpers import create_assistant_artifact


def _card_template_request(
    artifact_id: str,
    payload: dict[str, object],
) -> AssistantArtifactCreateRequest:
    return AssistantArtifactCreateRequest(
        id=artifact_id,
        kind="card_template",
        schema_version=1,
        payload_json={
            "id": f"card-{artifact_id}",
            "name": "Staged Card",
            "slot_default": "morning",
            "payload": payload,
        },
    )


def _capability_requests() -> list[dict[str, object]]:
    artifacts = SqliteArtifactRepository().list_assistant_artifacts(
        kind="capability_request", status=None
    )
    return [artifact.payload_json for artifact in artifacts]


def test_unsupported_card_type_records_capability_request():
    artifact = create_assistant_artifact(
        _card_template_request(
            "artifact-journal", {"card_type": "guided_journal", "prompts": []}
        )
    )

    assert artifact.status == "invalid"
    requests = _capability_requests()
    assert len(requests) == 1
    assert requests[0]["requested_card_type"] == "guided_journal"
    assert requests[0]["source_artifact_id"] == "artifact-journal"


def test_supported_card_type_with_invalid_payload_does_not_record_capability_request():
    artifact = create_assistant_artifact(
        # breath_timer is supported; the payload is invalid (missing required fields).
        _card_template_request("artifact-bad-breath", {"card_type": "breath_timer"})
    )

    assert artifact.status == "invalid"
    assert _capability_requests() == []


def test_missing_card_type_does_not_record_capability_request():
    artifact = create_assistant_artifact(
        _card_template_request("artifact-no-type", {"duration_minutes": 10})
    )

    assert artifact.status == "invalid"
    assert _capability_requests() == []


def test_valid_card_template_does_not_record_capability_request():
    artifact = create_assistant_artifact(
        _card_template_request(
            "artifact-valid-breath",
            {
                "card_type": "breath_timer",
                "duration_minutes": 10,
                "pattern_label": "5s in / 5s out",
            },
        )
    )

    assert artifact.status == "validated"
    assert _capability_requests() == []
