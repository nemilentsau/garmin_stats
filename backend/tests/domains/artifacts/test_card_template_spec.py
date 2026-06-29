"""CardTemplateSpec accepts typed payloads and rejects legacy renderer specs."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

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
