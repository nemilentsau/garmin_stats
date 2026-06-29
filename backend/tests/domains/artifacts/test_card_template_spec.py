"""CardTemplateSpec accepts typed payloads and rejects legacy renderer specs."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domains.artifacts.application.validation import validate_card_template_payload
from app.domains.artifacts.contracts import CardTemplateSpec


def test_card_template_spec_typed_payload():
    spec = CardTemplateSpec.model_validate(
        {
            "id": "c1",
            "name": "Weekly Review",
            "slot_default": "evening",
            "payload": {
                "card_type": "checklist",
                "items": [{"id": "q1", "label": "What worked?"}],
            },
        }
    )
    assert spec.payload.card_type == "checklist"


def test_card_template_spec_rejects_legacy_renderer_payload():
    with pytest.raises(ValidationError):
        CardTemplateSpec.model_validate(
            {
                "id": "c1",
                "name": "Old",
                "renderer": "checklist_block",
                "slot_default": "evening",
                "payload": {"items": []},  # no card_type discriminator
            }
        )


# ---------------------------------------------------------------------------
# validate_card_template_payload — regression tests for the full-spec shape
# ---------------------------------------------------------------------------


def test_validate_card_template_payload_valid():
    errors, payload = validate_card_template_payload(
        {"id": "c1", "name": "N", "slot_default": "evening",
         "payload": {"card_type": "checklist", "items": []}}
    )
    assert errors == []
    assert payload is not None
    assert payload.card_type == "checklist"


def test_validate_card_template_payload_missing_discriminator():
    errors, payload = validate_card_template_payload(
        {"id": "c1", "name": "N", "slot_default": "evening",
         "payload": {"items": []}}  # no card_type
    )
    assert errors
    assert payload is None
