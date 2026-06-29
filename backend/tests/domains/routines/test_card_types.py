"""Discriminated-union card payload/actual contracts.

Covers one valid payload per card_type, discriminator dispatch, and rejection
of an unknown card_type. Log round-trips live in test_card_logs below.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from app.domains.routines.contracts import (
    CardActual,
    CardPayload,
    ChecklistActual,
    ChecklistPayload,
    RunningWorkoutPayload,
    StrengthActual,
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


ACTUAL_ADAPTER = TypeAdapter(CardActual)


def test_strength_actual_marks_extra_work():
    actual = ACTUAL_ADAPTER.validate_python(
        {
            "card_type": "strength_session",
            "exercises": [
                {
                    "exercise_id": "pa1",
                    "is_extra": False,
                    "sets": [{"set_index": 1, "weight": 60.0, "reps": 8, "rir": 2}],
                },
                {
                    "exercise_id": None,
                    "label": "Face pulls (felt good)",
                    "is_extra": True,
                    "sets": [{"set_index": 1, "weight": 20.0, "reps": 15}],
                },
            ],
            "ratings": {"shoulder_comfort": 4},
        }
    )
    assert isinstance(actual, StrengthActual)
    extras = [e for e in actual.exercises if e.is_extra]
    assert extras[0].label == "Face pulls (felt good)"
    assert extras[0].exercise_id is None


def test_checklist_actual_round_trips():
    actual = ACTUAL_ADAPTER.validate_python(
        {
            "card_type": "checklist",
            "answers": [{"item_id": "q1", "checked": True, "text": "Resonance"}],
        }
    )
    assert isinstance(actual, ChecklistActual)
    assert actual.answers[0].text == "Resonance"
