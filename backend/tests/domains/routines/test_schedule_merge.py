"""Tests for merge_schedule_payload robustness.

Covers: invalid override key falls back to base payload; card_type override key
is stripped (no discriminator swap); valid override key is applied.
"""

from __future__ import annotations

from app.domains.routines.contracts import (
    CardTemplate,
    ChecklistPayload,
    RoutineAssignment,
)
from app.domains.routines.schedule import merge_schedule_payload


def _checklist_card(
    card_id: str = "c-merge",
    *,
    instructions: str = "base instructions",
) -> CardTemplate:
    return CardTemplate.model_validate(
        {
            "id": card_id,
            "name": "Merge Test Card",
            "slot_default": "morning",
            "payload_json": {
                "card_type": "checklist",
                "instructions": instructions,
                "items": [{"id": "q1", "label": "Q1"}],
            },
        }
    )


def _assignment(override: dict[str, object]) -> RoutineAssignment:
    return RoutineAssignment(
        id="a-merge",
        routine_id="r-merge",
        card_template_id="c-merge",
        date="2026-06-29",
        slot="morning",
        position=10,
        prescription_override_json=override,
    )


class TestMergeSchedulePayloadOverrideRobustness:
    def test_invalid_override_key_returns_base_payload_unchanged(self):
        """An unknown field in the override must not 500 — fall back to base payload."""
        card = _checklist_card()
        assignment = _assignment({"bogus_field": "nope"})

        result = merge_schedule_payload(card, assignment)

        assert isinstance(result, ChecklistPayload)
        assert result.instructions == "base instructions"

    def test_override_card_type_key_is_ignored(self):
        """card_type in an override must never swap the payload discriminator."""
        card = _checklist_card()
        assignment = _assignment({"card_type": "running_workout"})

        result = merge_schedule_payload(card, assignment)

        assert result.card_type == "checklist"

    def test_valid_override_key_is_applied(self):
        """A valid field in the override is merged into the resolved payload."""
        card = _checklist_card(instructions="base instructions")
        assignment = _assignment({"instructions": "override instructions"})

        result = merge_schedule_payload(card, assignment)

        assert isinstance(result, ChecklistPayload)
        assert result.instructions == "override instructions"

    def test_no_override_returns_base_payload_unchanged(self):
        """Assignment with empty override dict leaves payload untouched."""
        card = _checklist_card(instructions="pristine")
        assignment = _assignment({})

        result = merge_schedule_payload(card, assignment)

        assert isinstance(result, ChecklistPayload)
        assert result.instructions == "pristine"
