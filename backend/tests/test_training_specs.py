"""Tests for assistant artifacts and compiled training runtime."""

from app.infra.database import (
    load_assistant_artifacts,
    load_card_templates,
    load_routine_assignments,
    load_routine_schedules,
    save_card_override,
)
from app.models import AssistantArtifactCreateRequest, CardOverride, TodayCardLogUpdateRequest
from app.services.today import get_today, upsert_today_card_log
from app.services.training_specs import activate_assistant_artifact, create_assistant_artifact


def _card_request(
    card_id: str,
    *,
    renderer: str = "timer_session",
) -> AssistantArtifactCreateRequest:
    return AssistantArtifactCreateRequest(
        id=f"artifact-{card_id}",
        kind="card_template",
        schema_version=1,
        payload_json={
            "id": card_id,
            "name": f"Card {card_id}",
            "renderer": renderer,
            "slot_default": "evening",
            "summary": "Breath-led recovery card",
            "tags": ["mindfulness"],
            "payload": {
                "duration_minutes": 10,
                "pattern": "5s in / 5s out",
                "instructions": "Stay relaxed.",
                "rating_prompts": [
                    {"key": "clarity", "label": "Clarity", "scale_min": 1, "scale_max": 5}
                ],
            },
        },
    )


def _routine_request(
    routine_id: str,
    *,
    card_id: str,
    cadence: str = "weekly",
    cycle_week: int = 1,
    weekday: str = "monday",
) -> AssistantArtifactCreateRequest:
    return AssistantArtifactCreateRequest(
        id=f"artifact-{routine_id}",
        kind="routine_spec",
        schema_version=1,
        payload_json={
            "id": routine_id,
            "name": f"Routine {routine_id}",
            "cadence": cadence,
            "start_date": "2026-03-02",
            "status": "active",
            "tags": ["training"],
            "notes": "Compiled from assistant draft",
            "assignments": [
                {
                    "id": f"{routine_id}-assignment",
                    "card_template_id": card_id,
                    "cycle_week": cycle_week,
                    "weekday": weekday,
                    "slot": "evening",
                    "position": 20,
                    "prescription_override_json": {},
                }
            ],
        },
    )


class TestAssistantArtifactValidation:
    def test_supported_card_template_artifact_validates(self):
        artifact = create_assistant_artifact(_card_request("card-valid"))

        assert artifact.status == "validated"
        assert artifact.validation_errors == []

    def test_unsupported_renderer_creates_capability_request_artifact(self):
        artifact = create_assistant_artifact(
            _card_request("card-unsupported", renderer="guided_journal")
        )

        capability_requests = load_assistant_artifacts(kind="capability_request")

        assert artifact.status == "invalid"
        assert "Unsupported renderer family 'guided_journal'" in artifact.validation_errors[0]
        assert len(capability_requests) == 1
        assert capability_requests[0].payload_json["requested_renderer"] == "guided_journal"


class TestArtifactActivation:
    def test_activating_routine_compiles_card_routine_and_assignments(self):
        card_artifact = create_assistant_artifact(_card_request("card-compile"))
        routine_artifact = create_assistant_artifact(
            _routine_request("routine-compile", card_id="card-compile")
        )

        activate_assistant_artifact(card_artifact.id)
        activated = activate_assistant_artifact(routine_artifact.id)
        activate_assistant_artifact(routine_artifact.id)

        assert activated.status == "activated"
        assert [card.id for card in load_card_templates()] == ["card-compile"]
        assert [routine.id for routine in load_routine_schedules()] == ["routine-compile"]
        assignments = load_routine_assignments("routine-compile")
        assert len(assignments) == 1
        assert assignments[0].card_template_id == "card-compile"


class TestTodayProjection:
    def test_today_uses_only_activated_routines_and_supports_overlap(self):
        create_assistant_artifact(_card_request("card-live"))
        create_assistant_artifact(_card_request("card-draft"))
        live_weekly = create_assistant_artifact(
            _routine_request("routine-weekly", card_id="card-live", cadence="weekly")
        )
        live_biweekly = create_assistant_artifact(
            _routine_request(
                "routine-biweekly",
                card_id="card-live",
                cadence="biweekly",
                cycle_week=1,
            )
        )
        create_assistant_artifact(
            _routine_request("routine-draft", card_id="card-draft", cadence="weekly")
        )

        activate_assistant_artifact("artifact-card-live")
        activate_assistant_artifact(live_weekly.id)
        activate_assistant_artifact(live_biweekly.id)

        today = get_today("2026-03-02")
        all_cards = [card for slot in today.slots for card in slot.cards]

        assert len(all_cards) == 2
        assert {card.routine_id for card in all_cards} == {"routine-weekly", "routine-biweekly"}
        assert {card.card_template_id for card in all_cards} == {"card-live"}

    def test_card_log_round_trips_into_today_projection(self):
        card_artifact = create_assistant_artifact(_card_request("card-main"))
        routine_artifact = create_assistant_artifact(
            _routine_request("routine-main", card_id="card-main")
        )

        activate_assistant_artifact(card_artifact.id)
        activate_assistant_artifact(routine_artifact.id)

        today_before = get_today("2026-03-02")
        scheduled_card = today_before.slots[2].cards[0]

        upsert_today_card_log(
            "2026-03-02",
            scheduled_card.occurrence_key,
            TodayCardLogUpdateRequest(
                card_template_id=scheduled_card.card_template_id,
                assignment_id=scheduled_card.assignment_id,
                status="partial",
                actual_json={"actual_minutes": 8, "ratings": {"clarity": 4}},
                notes="Shortened after the run",
            ),
        )
        today_with_log = get_today("2026-03-02")
        logged_card = today_with_log.slots[2].cards[0]

        assert logged_card.status == "partial"
        assert logged_card.actual_json["actual_minutes"] == 8
        assert logged_card.notes == "Shortened after the run"

    def test_today_applies_persisted_add_and_hide_overrides(self):
        card_artifact = create_assistant_artifact(_card_request("card-main"))
        extra_card_artifact = create_assistant_artifact(_card_request("card-extra"))
        routine_artifact = create_assistant_artifact(
            _routine_request("routine-main", card_id="card-main")
        )

        activate_assistant_artifact(card_artifact.id)
        activate_assistant_artifact(extra_card_artifact.id)
        activate_assistant_artifact(routine_artifact.id)

        today_before = get_today("2026-03-02")
        scheduled_card = today_before.slots[2].cards[0]

        save_card_override(
            CardOverride(
                id="override-extra",
                date="2026-03-02",
                action="add",
                card_template_id="card-extra",
                slot="morning",
                position=5,
            )
        )
        save_card_override(
            CardOverride(
                id="override-hide-main",
                date="2026-03-02",
                action="hide",
                target_occurrence_key=scheduled_card.occurrence_key,
            )
        )

        today_after = get_today("2026-03-02")
        all_cards = [card for slot in today_after.slots for card in slot.cards]

        assert [card.card_template_id for card in all_cards] == ["card-extra"]
        assert all_cards[0].occurrence_key == "override:add:override-extra:2026-03-02"
        assert all_cards[0].slot == "morning"

    def test_today_applies_persisted_replace_overrides(self):
        card_artifact = create_assistant_artifact(_card_request("card-main"))
        extra_card_artifact = create_assistant_artifact(_card_request("card-extra"))
        routine_artifact = create_assistant_artifact(
            _routine_request("routine-main", card_id="card-main")
        )

        activate_assistant_artifact(card_artifact.id)
        activate_assistant_artifact(extra_card_artifact.id)
        activate_assistant_artifact(routine_artifact.id)

        today_before = get_today("2026-03-02")
        scheduled_card = today_before.slots[2].cards[0]

        save_card_override(
            CardOverride(
                id="override-replace-main",
                date="2026-03-02",
                action="replace",
                target_occurrence_key=scheduled_card.occurrence_key,
                card_template_id="card-extra",
            )
        )

        today_after = get_today("2026-03-02")
        all_cards = [card for slot in today_after.slots for card in slot.cards]

        assert [card.card_template_id for card in all_cards] == ["card-extra"]
        assert all_cards[0].occurrence_key == "override:replace:override-replace-main:2026-03-02"
        assert all_cards[0].slot == scheduled_card.slot
        assert all_cards[0].routine_id == scheduled_card.routine_id
