"""Discriminated-union card payload/actual contracts.

Covers one valid payload per card_type, discriminator dispatch, and rejection
of an unknown card_type. Log round-trips live in test_card_logs below.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from app.domains.routines.contracts import (
    CardPayload,
    ChecklistPayload,
    RunningWorkoutPayload,
    StrengthSessionPayload,
)

PAYLOAD_ADAPTER = TypeAdapter(CardPayload)


def test_checklist_payload_dispatches_by_card_type():
    payload = PAYLOAD_ADAPTER.validate_python(
        {
            "card_type": "checklist",
            "instructions": "Weekly review",
            "items": [{"id": "q1", "label": "What worked?"}],
            "domain": "breathwork",
        }
    )
    assert isinstance(payload, ChecklistPayload)
    assert payload.items[0].id == "q1"


def test_running_payload_promotes_structured_fields():
    payload = PAYLOAD_ADAPTER.validate_python(
        {
            "card_type": "running_workout",
            "workout_type": "easy_plus_strides",
            "calibration_quality": True,
            "segments": [
                {
                    "id": "warmup",
                    "label": "Easy running",
                    "kind": "warmup",
                    "prescription": "35-50 min",
                }
            ],
        }
    )
    assert isinstance(payload, RunningWorkoutPayload)
    assert payload.segments[0].kind == "warmup"


def test_strength_payload_carries_set_scheme_and_ratings():
    payload = PAYLOAD_ADAPTER.validate_python(
        {
            "card_type": "strength_session",
            "exercises": [{"id": "pa1", "label": "Bench", "set_scheme": "3x5-8"}],
            "rating_prompts": [{"key": "shoulder_comfort", "label": "Shoulder comfort"}],
        }
    )
    assert isinstance(payload, StrengthSessionPayload)
    assert payload.exercises[0].set_scheme == "3x5-8"


def test_unknown_card_type_is_rejected():
    with pytest.raises(ValidationError):
        PAYLOAD_ADAPTER.validate_python({"card_type": "nope"})
