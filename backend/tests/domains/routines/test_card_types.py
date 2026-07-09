"""Discriminated-union card payload/actual contracts.

Covers one valid payload per card_type, discriminator dispatch, rejection of an
unknown card_type, and coercion of empty/missing actual_json to None on CardLog,
TodayCard, and TodayCardLogUpdateRequest.
"""

from __future__ import annotations

import logging

import pytest
from pydantic import TypeAdapter, ValidationError

from app.domains.routines.contracts import (
    CardActual,
    CardLog,
    CardPayload,
    CardTemplate,
    ChecklistActual,
    ChecklistAnswer,
    ChecklistItem,
    ChecklistPayload,
    RunningWorkoutPayload,
    ScheduleOccurrence,
    StrengthActual,
    StrengthSessionPayload,
    TimerActual,
    TodayCard,
    TodayCardLogUpdateRequest,
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


def test_payload_variant_fields_default_empty():
    """variant_options/selection_rule default to empty on all three variant-eligible payloads."""
    running = RunningWorkoutPayload(card_type="running_workout", workout_type="Easy")
    strength = StrengthSessionPayload(card_type="strength_session")
    checklist = ChecklistPayload(card_type="checklist")
    for payload in (running, strength, checklist):
        assert payload.variant_options == []
        assert payload.selection_rule is None


def test_payload_variant_fields_are_settable():
    payload = RunningWorkoutPayload(
        card_type="running_workout",
        workout_type="Easy",
        variant_options=["standard", "reduced volume"],
        selection_rule="Pick reduced volume if quad soreness >= 2.",
    )
    assert payload.variant_options == ["standard", "reduced volume"]
    assert payload.selection_rule == "Pick reduced volume if quad soreness >= 2."


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


def test_checklist_item_kind_defaults_to_checkbox_and_accepts_tissue_check():
    item = ChecklistItem(id="tissue.quad", label="quad")
    assert item.kind == "checkbox"
    typed = ChecklistItem(id="tissue.quad", label="quad", kind="tissue_check")
    assert typed.kind == "tissue_check"


def test_checklist_answer_carries_scale_and_flag():
    answer = ChecklistAnswer(item_id="tissue.quad", scale=2, flagged=True)
    assert (answer.scale, answer.flagged, answer.checked) == (2, True, False)


def test_checklist_answer_rejects_scale_out_of_range():
    with pytest.raises(ValidationError):
        ChecklistAnswer(item_id="tissue.quad", scale=4)


def test_card_template_payload_is_typed_union():
    card = CardTemplate.model_validate(
        {
            "id": "c1",
            "name": "Breathwork Weekly Review",
            "slot_default": "evening",
            "payload_json": {
                "card_type": "checklist",
                "items": [{"id": "q1", "label": "What worked?"}],
            },
        }
    )
    assert card.payload_json.card_type == "checklist"
    assert not hasattr(card, "renderer")


def test_schedule_occurrence_has_no_renderer():
    occ = ScheduleOccurrence.model_validate(
        {
            "occurrence_key": "k",
            "date": "2026-06-29",
            "slot": "evening",
            "source_kind": "scheduled",
            "card_template_id": "c1",
            "name": "x",
            "payload_json": {"card_type": "checklist"},
        }
    )
    assert occ.payload_json.card_type == "checklist"
    assert not hasattr(occ, "renderer")


# ---------------------------------------------------------------------------
# Bug 1: empty / missing card_type in actual_json must coerce to None
# ---------------------------------------------------------------------------

_CARD_LOG_BASE = {
    "id": "log-1",
    "date": "2026-06-29",
    "occurrence_key": "scheduled:a:2026-06-29",
    "card_template_id": "c1",
}

_TODAY_CARD_BASE = {
    "occurrence_key": "scheduled:a:2026-06-29",
    "date": "2026-06-29",
    "slot": "morning",
    "source_kind": "scheduled",
    "card_template_id": "c1",
    "name": "My Card",
    "payload_json": {"card_type": "checklist"},
}


def test_breath_payload_rejects_phases():
    # phases was removed from the schema; extra keys are forbidden
    with pytest.raises(ValidationError):
        PAYLOAD_ADAPTER.validate_python(
            {"card_type": "breath_timer", "duration_minutes": 5,
             "pattern_label": "5s in / 5s out", "phases": [{"kind": "inhale", "seconds": 5}]}
        )


def test_breath_payload_valid_without_phases():
    p = PAYLOAD_ADAPTER.validate_python(
        {"card_type": "breath_timer", "duration_minutes": 10, "pattern_label": "5s in / 5s out"}
    )
    assert p.card_type == "breath_timer"
    assert not hasattr(p, "phases")


def test_timer_actual_has_no_completed_cycles():
    a = ACTUAL_ADAPTER.validate_python(
        {"card_type": "breath_timer", "ratings": {"felt_downshift": 2}}
    )
    assert a.ratings["felt_downshift"] == 2
    assert not hasattr(a, "completed_cycles")


class TestEmptyActualJsonCoercedToNone:
    def test_card_log_empty_dict_actual_json_coerces_to_none(self):
        """Legacy rows with actual_json={} must load without 500."""
        log = CardLog.model_validate({**_CARD_LOG_BASE, "actual_json": {}})
        assert log.actual_json is None

    def test_card_log_valid_typed_actual_is_preserved(self):
        """A properly typed actual_json is NOT coerced away."""
        log = CardLog.model_validate(
            {
                **_CARD_LOG_BASE,
                "actual_json": {"card_type": "checklist", "answers": []},
            }
        )
        assert log.actual_json is not None
        assert log.actual_json.card_type == "checklist"

    def test_card_log_none_actual_json_stays_none(self):
        """Explicit None stays None."""
        log = CardLog.model_validate({**_CARD_LOG_BASE, "actual_json": None})
        assert log.actual_json is None

    def test_today_card_empty_dict_actual_json_coerces_to_none(self):
        """TodayCard with actual_json={} must not 500 on the Today-board load path."""
        card = TodayCard.model_validate({**_TODAY_CARD_BASE, "actual_json": {}})
        assert card.actual_json is None

    def test_today_card_valid_typed_actual_is_preserved(self):
        card = TodayCard.model_validate(
            {
                **_TODAY_CARD_BASE,
                "actual_json": {"card_type": "checklist", "answers": []},
            }
        )
        assert card.actual_json is not None
        assert isinstance(card.actual_json, ChecklistActual)

    def test_today_card_log_update_request_empty_dict_coerces_to_none(self):
        """TodayCardLogUpdateRequest with actual_json={} from a client must not 500."""
        req = TodayCardLogUpdateRequest.model_validate(
            {
                "card_template_id": "c1",
                "status": "completed",
                "actual_json": {},
            }
        )
        assert req.actual_json is None

    def test_today_card_log_update_request_valid_typed_actual_is_preserved(self):
        req = TodayCardLogUpdateRequest.model_validate(
            {
                "card_template_id": "c1",
                "status": "completed",
                "actual_json": {"card_type": "checklist", "answers": []},
            }
        )
        assert req.actual_json is not None
        assert req.actual_json.card_type == "checklist"


# ---------------------------------------------------------------------------
# Legacy stored actual_json shapes must load without 500 (reads are tolerant),
# while client-sent bodies stay strict (writes reject unknown shapes).
# ---------------------------------------------------------------------------


class TestLegacyStoredActualJsonNormalization:
    def test_card_log_actual_with_removed_field_loads_and_drops_it(self):
        """The live 2026-06-29 row: breath actual with removed completed_cycles."""
        log = CardLog.model_validate(
            {
                **_CARD_LOG_BASE,
                "actual_json": {
                    "card_type": "breath_timer",
                    "ratings": {},
                    "completed_cycles": 0,
                },
            }
        )
        assert log.actual_json is not None
        assert log.actual_json.card_type == "breath_timer"
        assert not hasattr(log.actual_json, "completed_cycles")

    def test_today_card_actual_with_removed_field_loads_and_drops_it(self):
        card = TodayCard.model_validate(
            {
                **_TODAY_CARD_BASE,
                "actual_json": {
                    "card_type": "breath_timer",
                    "ratings": {"felt_downshift": 2},
                    "completed_cycles": 4,
                },
            }
        )
        assert isinstance(card.actual_json, TimerActual)
        assert card.actual_json.ratings == {"felt_downshift": 2}

    def test_card_log_nonempty_actual_without_card_type_nulls_with_warning(
        self, caplog: pytest.LogCaptureFixture
    ):
        """Old untyped shapes can't be dispatched; null them loudly, never crash."""
        with caplog.at_level(logging.WARNING):
            log = CardLog.model_validate(
                {
                    **_CARD_LOG_BASE,
                    "actual_json": {"actual_minutes": 12, "ratings": {"clarity": 4}},
                }
            )
        assert log.actual_json is None
        assert any("actual_json" in record.message for record in caplog.records)

    def test_card_log_unknown_card_type_actual_nulls_instead_of_raising(self):
        log = CardLog.model_validate(
            {
                **_CARD_LOG_BASE,
                "actual_json": {"card_type": "guided_journal", "entries": []},
            }
        )
        assert log.actual_json is None

    def test_update_request_rejects_unknown_actual_field(self):
        """Write path stays strict: clients get a 422, not silent stripping."""
        with pytest.raises(ValidationError):
            TodayCardLogUpdateRequest.model_validate(
                {
                    "card_template_id": "c1",
                    "actual_json": {
                        "card_type": "breath_timer",
                        "ratings": {},
                        "completed_cycles": 3,
                    },
                }
            )

    def test_update_request_rejects_nonempty_actual_without_card_type(self):
        """Write path stays strict: an undispatchable non-empty actual is a client error."""
        with pytest.raises(ValidationError):
            TodayCardLogUpdateRequest.model_validate(
                {
                    "card_template_id": "c1",
                    "actual_json": {"actual_minutes": 12},
                }
            )
