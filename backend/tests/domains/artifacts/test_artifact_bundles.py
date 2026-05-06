"""Tests for assistant artifacts and compiled routine runtime."""

import json
from typing import Any, cast

import pytest

from app.infra.database import (
    load_assistant_artifacts,
    load_card_template,
    load_card_templates,
    load_routine_assignments,
    load_routine_schedules,
    save_card_override,
)
from app.models import (
    ArtifactBundleSpec,
    AssistantArtifactCreateRequest,
    CardOverride,
    TodayCardLogUpdateRequest,
)
from tests._architecture import REPO_ROOT
from tests._artifact_helpers import (
    activate_assistant_artifact,
    create_assistant_artifact,
    import_artifact_bundle,
    preview_artifact_bundle,
)
from tests._routines_helpers import get_schedule_window, get_today, upsert_today_card_log

_CORE_BUNDLE_PATH = REPO_ROOT / "docs" / "two_week_core_bundle.json"
_MEDITATION_BUNDLE_PATH = REPO_ROOT / "docs" / "two_week_meditation_bundle.json"


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
    day: int = 1,
) -> AssistantArtifactCreateRequest:
    return AssistantArtifactCreateRequest(
        id=f"artifact-{routine_id}",
        kind="routine_spec",
        schema_version=1,
        payload_json={
            "id": routine_id,
            "name": f"Routine {routine_id}",
            "start_date": "2026-03-02",
            "status": "active",
            "tags": ["training"],
            "notes": "Compiled from assistant draft",
            "assignments": [
                {
                    "id": f"{routine_id}-assignment",
                    "card_template_id": card_id,
                    "day": day,
                    "slot": "evening",
                    "position": 20,
                    "prescription_override_json": {},
                }
            ],
        },
    )


def _bundle_spec(
    *,
    card_id: str = "bundle-card",
    routine_id: str = "bundle-routine",
    card_templates: list[dict[str, object]] | None = None,
    routine_specs: list[dict[str, object]] | None = None,
) -> ArtifactBundleSpec:
    return ArtifactBundleSpec.model_validate(
        {
            "id": "bundle-spec",
            "name": "Bundle Spec",
            "schema_version": 1,
            "card_templates": card_templates
            if card_templates is not None
            else [_card_request(card_id).payload_json],
            "routine_specs": routine_specs
            if routine_specs is not None
            else [_routine_request(routine_id, card_id=card_id).payload_json],
        }
    )


def _load_meditation_bundle() -> ArtifactBundleSpec:
    return ArtifactBundleSpec.model_validate(
        json.loads(_MEDITATION_BUNDLE_PATH.read_text(encoding="utf-8"))
    )


def _load_core_bundle() -> ArtifactBundleSpec:
    return ArtifactBundleSpec.model_validate(
        json.loads(_CORE_BUNDLE_PATH.read_text(encoding="utf-8"))
    )


def _starter_bundle_spec() -> ArtifactBundleSpec:
    return ArtifactBundleSpec.model_validate(
        {
            "id": "proper-routine-bundle",
            "name": "Proper Routine Bundle",
            "schema_version": 1,
            "description": (
                "Starter proper-spec bundle. Replace with LLM-authored JSON before "
                "previewing."
            ),
            "card_templates": [
                {
                    "id": "starter-breathing-card",
                    "name": "Starter Breathing Card",
                    "renderer": "timer_session",
                    "slot_default": "morning",
                    "summary": "Reusable breathwork card template.",
                    "tags": ["starter", "breathwork"],
                    "payload": {
                        "duration_minutes": 8,
                        "pattern": "5s in / 5s out",
                        "instructions": "Keep the breath smooth and relaxed.",
                        "rating_prompts": [
                            {
                                "key": "attention_stability",
                                "label": "Attention stability",
                                "scale_min": 1,
                                "scale_max": 5,
                            }
                        ],
                    },
                }
            ],
            "routine_specs": [
                {
                    "id": "starter-routine",
                    "name": "Starter Routine",
                    "start_date": "2026-03-16",
                    "status": "active",
                    "tags": ["starter"],
                    "notes": "One routine schedule driven by the proper bundle format.",
                    "assignments": [
                        {
                            "id": "starter-routine-day1-morning",
                            "card_template_id": "starter-breathing-card",
                            "day": 1,
                            "slot": "morning",
                            "position": 10,
                            "prescription_override_json": {
                                "duration_minutes": 10,
                                "instructions": (
                                    "Assignment overrides change dose without creating a new "
                                    "card template."
                                ),
                            },
                        }
                    ],
                }
            ],
        }
    )


def _exercise_list(payload_json: dict[str, object]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], payload_json["exercises"])


def _bundle_card_spec(
    card_id: str,
    *,
    name: str,
    duration_minutes: int,
) -> dict[str, object]:
    return {
        "id": card_id,
        "name": name,
        "renderer": "timer_session",
        "slot_default": "evening",
        "summary": "Breath-led recovery card",
        "tags": ["mindfulness"],
        "payload": {
            "duration_minutes": duration_minutes,
            "pattern": "5s in / 5s out",
            "instructions": f"Practice {name.lower()}",
            "rating_prompts": [
                {"key": "clarity", "label": "Clarity", "scale_min": 1, "scale_max": 5}
            ],
        },
    }


def _bundle_routine_spec(
    routine_id: str,
    *,
    card_id: str,
    assignment_id: str,
    day: int = 1,
) -> dict[str, object]:
    return {
        "id": routine_id,
        "name": f"Routine {routine_id}",
        "start_date": "2026-03-02",
        "status": "active",
        "tags": ["training"],
        "notes": "Compiled from bundle import",
        "assignments": [
            {
                "id": assignment_id,
                "card_template_id": card_id,
                "day": day,
                "slot": "evening",
                "position": 20,
                "prescription_override_json": {},
            }
        ],
    }


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

    def test_activating_routine_refreshes_live_card_from_newer_validated_draft(self):
        first_card_artifact = create_assistant_artifact(_card_request("card-refresh"))
        activate_assistant_artifact(first_card_artifact.id)

        updated_card_request = _card_request("card-refresh")
        updated_card_request.payload_json["name"] = "Card refreshed"
        updated_payload = cast(
            dict[str, object],
            updated_card_request.payload_json["payload"],
        )
        updated_payload["duration_minutes"] = 14
        updated_card_request = updated_card_request.model_copy(
            update={"id": "artifact-card-refresh-v2"}
        )
        create_assistant_artifact(updated_card_request)

        routine_artifact = create_assistant_artifact(
            _routine_request("routine-refresh", card_id="card-refresh")
        )

        activate_assistant_artifact(routine_artifact.id)

        card = load_card_template("card-refresh")

        assert card is not None
        assert card.name == "Card refreshed"
        assert card.payload_json["duration_minutes"] == 14
        assert card.source_artifact_id == "artifact-card-refresh-v2"


class TestArtifactBundles:
    def test_preview_bundle_returns_create_deltas_without_persisting(self):
        preview = preview_artifact_bundle(_bundle_spec())

        assert preview.valid is True
        assert [delta.kind for delta in preview.deltas] == ["card_template", "routine_spec"]
        assert [delta.action for delta in preview.deltas] == ["create", "create"]
        assert load_assistant_artifacts() == []
        assert load_card_templates() == []
        assert load_routine_schedules() == []

    def test_preview_bundle_reports_duplicate_card_ids(self):
        duplicate_card = _card_request("duplicate-card").payload_json
        preview = preview_artifact_bundle(
            _bundle_spec(card_templates=[duplicate_card, duplicate_card], routine_specs=[])
        )

        assert preview.valid is False
        assert "Duplicate card_template id 'duplicate-card'" in preview.issues[0].message

    def test_preview_bundle_reports_unknown_card_reference(self):
        preview = preview_artifact_bundle(
            _bundle_spec(
                card_templates=[],
                routine_specs=[
                    _routine_request("bundle-routine", card_id="missing-card").payload_json
                ],
            )
        )

        assert preview.valid is False
        assert "unknown card template 'missing-card'" in preview.issues[0].message

    def test_import_bundle_saves_validated_drafts_without_compiling_live_runtime(self):
        result = import_artifact_bundle(_bundle_spec())

        artifacts = load_assistant_artifacts()

        assert result.total_imported == 2
        assert [artifact.status for artifact in artifacts] == ["validated", "validated"]
        assert {artifact.kind for artifact in artifacts} == {"routine_spec", "card_template"}
        assert load_card_templates() == []
        assert load_routine_schedules() == []

    def test_preview_bundle_rejects_reserved_placeholder_content(self):
        preview = preview_artifact_bundle(_starter_bundle_spec())

        assert preview.valid is False
        assert load_assistant_artifacts() == []
        assert {issue.path for issue in preview.issues} >= {
            "bundle.id",
            "bundle.name",
            "bundle.description",
            "card_templates.0.id",
            "card_templates.0.tags",
            "routine_specs.0.id",
            "routine_specs.0.tags",
            "routine_specs.0.assignments.0.id",
        }
        assert any("placeholder/demo content" in issue.message for issue in preview.issues)

    def test_import_bundle_rejects_reserved_placeholder_content(self):
        with pytest.raises(
            ValueError,
            match="Bundle has blocking issues; preview and resolve them before import",
        ):
            import_artifact_bundle(_starter_bundle_spec())

    def test_activating_older_bundle_routine_uses_matching_card_revision(self):
        first_bundle = _bundle_spec(
            card_id="shared-card",
            routine_id="shared-routine",
            card_templates=[
                _bundle_card_spec(
                    "shared-card",
                    name="First Revision",
                    duration_minutes=8,
                )
            ],
            routine_specs=[
                _bundle_routine_spec(
                    "shared-routine",
                    card_id="shared-card",
                    assignment_id="shared-routine-assignment",
                )
            ],
        )
        second_bundle = _bundle_spec(
            card_id="shared-card",
            routine_id="shared-routine",
            card_templates=[
                _bundle_card_spec(
                    "shared-card",
                    name="Second Revision",
                    duration_minutes=14,
                )
            ],
            routine_specs=[
                _bundle_routine_spec(
                    "shared-routine",
                    card_id="shared-card",
                    assignment_id="shared-routine-assignment",
                )
            ],
        )

        first_import = import_artifact_bundle(first_bundle)
        import_artifact_bundle(second_bundle)
        first_routine_artifact_id = next(
            delta.artifact_id for delta in first_import.deltas if delta.kind == "routine_spec"
        )

        activate_assistant_artifact(first_routine_artifact_id)

        card = load_card_template("shared-card")

        assert card is not None
        assert card.name == "First Revision"
        assert card.payload_json["duration_minutes"] == 8

    def test_activating_bundle_routine_updates_existing_live_card_to_bundle_revision(self):
        create_assistant_artifact(_card_request("shared-card"))
        activate_assistant_artifact("artifact-shared-card")

        imported = import_artifact_bundle(
            _bundle_spec(
                card_id="shared-card",
                routine_id="bundle-routine",
                card_templates=[
                    _bundle_card_spec(
                        "shared-card",
                        name="Updated Bundle Revision",
                        duration_minutes=12,
                    )
                ],
                routine_specs=[
                    _bundle_routine_spec(
                        "bundle-routine",
                        card_id="shared-card",
                        assignment_id="bundle-routine-assignment",
                    )
                ],
            )
        )
        routine_artifact_id = next(
            delta.artifact_id for delta in imported.deltas if delta.kind == "routine_spec"
        )
        card_artifact_id = next(
            delta.artifact_id for delta in imported.deltas if delta.kind == "card_template"
        )

        activate_assistant_artifact(routine_artifact_id)

        card = load_card_template("shared-card")

        assert card is not None
        assert card.name == "Updated Bundle Revision"
        assert card.payload_json["duration_minutes"] == 12
        assert card.source_artifact_id == card_artifact_id

    def test_preview_bundle_reports_assignment_id_collision_with_existing_live_routine(self):
        create_assistant_artifact(_card_request("existing-card"))
        create_assistant_artifact(_routine_request("existing-routine", card_id="existing-card"))
        activate_assistant_artifact("artifact-existing-routine")

        preview = preview_artifact_bundle(
            _bundle_spec(
                card_id="bundle-card",
                routine_id="bundle-routine",
                card_templates=[
                    _bundle_card_spec(
                        "bundle-card",
                        name="Bundle Card",
                        duration_minutes=9,
                    )
                ],
                routine_specs=[
                    _bundle_routine_spec(
                        "bundle-routine",
                        card_id="bundle-card",
                        assignment_id="existing-routine-assignment",
                        day=2,
                    )
                ],
            )
        )

        assert preview.valid is False
        assert "already belongs to routine existing-routine" in preview.issues[0].message

    def test_preview_bundle_reports_assignment_id_collision_with_validated_draft(self):
        create_assistant_artifact(_card_request("draft-card"))
        create_assistant_artifact(_routine_request("draft-routine", card_id="draft-card"))

        preview = preview_artifact_bundle(
            _bundle_spec(
                card_id="bundle-card",
                routine_id="bundle-routine",
                card_templates=[
                    _bundle_card_spec(
                        "bundle-card",
                        name="Bundle Card",
                        duration_minutes=9,
                    )
                ],
                routine_specs=[
                    _bundle_routine_spec(
                        "bundle-routine",
                        card_id="bundle-card",
                        assignment_id="draft-routine-assignment",
                        day=3,
                    )
                ],
            )
        )

        assert preview.valid is False
        assert "already belongs to routine draft-routine" in preview.issues[0].message

    def test_imported_meditation_bundle_activates_and_resolves_expected_occurrences(self):
        bundle = _load_meditation_bundle()
        preview = preview_artifact_bundle(bundle)

        assert preview.valid is True
        assert len(preview.deltas) == 7

        imported = import_artifact_bundle(bundle)
        routine_artifact_ids = [
            delta.artifact_id for delta in imported.deltas if delta.kind == "routine_spec"
        ]

        assert len(routine_artifact_ids) == 1

        activate_assistant_artifact(routine_artifact_ids[0])

        window = get_schedule_window("2026-03-16")
        day1 = next(day for day in window.days if day.date == "2026-03-16")
        day8 = next(day for day in window.days if day.date == "2026-03-23")
        day12 = next(day for day in window.days if day.date == "2026-03-27")

        assert window.start_date == "2026-03-16"
        assert window.end_date == "2026-03-29"
        assert [occurrence.name for occurrence in day1.occurrences] == [
            "Resonance Breathing",
            "Extended Exhale",
        ]
        assert [
            occurrence.payload_json["duration_minutes"] for occurrence in day1.occurrences
        ] == [8, 6]
        assert [occurrence.slot for occurrence in day8.occurrences] == [
            "morning",
            "midday",
            "evening",
        ]
        assert [occurrence.name for occurrence in day8.occurrences] == [
            "Resonance Breathing",
            "Box Breathing",
            "Extended Exhale",
        ]
        assert day12.occurrences[2].name == "Open Monitoring"
        assert "Extended Exhale instead" in str(day12.occurrences[2].payload_json["instructions"])

        today = get_today("2026-03-16")
        all_cards = [card for slot in today.slots for card in slot.cards]

        assert [card.name for card in all_cards] == ["Resonance Breathing", "Extended Exhale"]
        assert [card.payload_json["duration_minutes"] for card in all_cards] == [8, 6]

    def test_core_bundle_runs_preview_import_activation_schedule_and_today_workflow(self):
        bundle = _load_core_bundle()

        preview = preview_artifact_bundle(bundle)

        assert preview.valid is True
        assert len(preview.issues) == 0
        assert len(preview.deltas) == 8
        assert load_assistant_artifacts() == []

        imported = import_artifact_bundle(bundle)
        routine_artifact_ids = [
            delta.artifact_id for delta in imported.deltas if delta.kind == "routine_spec"
        ]

        assert imported.total_imported == 8
        assert len(routine_artifact_ids) == 1

        activate_assistant_artifact(routine_artifact_ids[0])

        window = get_schedule_window("2026-03-16")
        day1 = next(day for day in window.days if day.date == "2026-03-16")
        day2 = next(day for day in window.days if day.date == "2026-03-17")
        day5 = next(day for day in window.days if day.date == "2026-03-20")
        day12 = next(day for day in window.days if day.date == "2026-03-27")
        day14 = next(day for day in window.days if day.date == "2026-03-29")

        assert window.start_date == "2026-03-16"
        assert window.end_date == "2026-03-29"
        assert [occurrence.name for occurrence in day1.occurrences] == ["Core Day A"]
        assert [occurrence.name for occurrence in day2.occurrences] == [
            "Core Day B",
            "Supporting Block 1",
        ]
        assert [occurrence.name for occurrence in day5.occurrences] == [
            "Core Day A",
            "Supporting Block 1",
            "Supporting Block 2",
        ]
        assert [occurrence.name for occurrence in day12.occurrences] == [
            "Core Day D",
            "Supporting Block 1",
            "Supporting Block 2",
            "Supporting Block 3",
        ]
        assert [occurrence.name for occurrence in day14.occurrences] == [
            "Core Day B",
            "Supporting Block 1",
            "Supporting Block 2",
        ]
        assert _exercise_list(day1.occurrences[0].payload_json)[0]["reps"] == "2x8 each side"
        assert _exercise_list(day12.occurrences[0].payload_json)[3]["label"] == "Turkish get-up"
        assert _exercise_list(day12.occurrences[3].payload_json)[0]["reps"] == "3x4"
        assert _exercise_list(day14.occurrences[0].payload_json)[3]["reps"] == "2x30s"

        today = get_today("2026-03-27")
        all_cards = [card for slot in today.slots for card in slot.cards]

        assert [card.name for card in all_cards] == [
            "Core Day D",
            "Supporting Block 1",
            "Supporting Block 2",
            "Supporting Block 3",
        ]

        upsert_today_card_log(
            "2026-03-27",
            all_cards[0].occurrence_key,
            TodayCardLogUpdateRequest(
                card_template_id=all_cards[0].card_template_id,
                assignment_id=all_cards[0].assignment_id,
                status="completed",
                actual_json={
                    "item_states": {
                        "d1": True,
                        "d2": True,
                        "d3": True,
                        "d4": False,
                    }
                },
                notes="Core block completed before strength session.",
            ),
        )

        updated_today = get_today("2026-03-27")
        updated_cards = [card for slot in updated_today.slots for card in slot.cards]
        updated_core = next(
            card for card in updated_cards if card.occurrence_key == all_cards[0].occurrence_key
        )

        assert updated_core.status == "completed"
        item_states = cast(dict[str, bool], updated_core.actual_json["item_states"])
        assert item_states["d3"] is True
        assert updated_core.notes == "Core block completed before strength session."


class TestTodayProjection:
    def test_today_uses_only_activated_routines_and_supports_overlap(self):
        create_assistant_artifact(_card_request("card-live"))
        create_assistant_artifact(_card_request("card-draft"))
        live_routine_a = create_assistant_artifact(
            _routine_request("routine-a", card_id="card-live", day=1)
        )
        live_routine_b = create_assistant_artifact(
            _routine_request("routine-b", card_id="card-live", day=1)
        )
        create_assistant_artifact(
            _routine_request("routine-draft", card_id="card-draft", day=1)
        )

        activate_assistant_artifact("artifact-card-live")
        activate_assistant_artifact(live_routine_a.id)
        activate_assistant_artifact(live_routine_b.id)

        today = get_today("2026-03-02")
        all_cards = [card for slot in today.slots for card in slot.cards]

        assert len(all_cards) == 2
        assert {card.routine_id for card in all_cards} == {"routine-a", "routine-b"}
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

    def test_today_log_rejects_missing_occurrence(self):
        with pytest.raises(LookupError, match="Today occurrence scheduled:missing:2026-03-02"):
            upsert_today_card_log(
                "2026-03-02",
                "scheduled:missing:2026-03-02",
                TodayCardLogUpdateRequest(
                    card_template_id="card-main",
                    status="completed",
                ),
            )

    def test_today_log_rejects_card_template_mismatch(self):
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

        with pytest.raises(ValueError, match="Card template does not match"):
            upsert_today_card_log(
                "2026-03-02",
                scheduled_card.occurrence_key,
                TodayCardLogUpdateRequest(
                    card_template_id="card-extra",
                    assignment_id=scheduled_card.assignment_id,
                    status="completed",
                ),
            )

        today_after = get_today("2026-03-02")

        assert today_after.slots[2].cards[0].status == "pending"

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

    def test_today_matches_schedule_projection_when_overrides_exist(self):
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

        schedule_day = get_schedule_window("2026-03-02", duration_days=1).days[0]
        today_after = get_today("2026-03-02")

        schedule_keys = [occurrence.occurrence_key for occurrence in schedule_day.occurrences]
        today_keys = [
            card.occurrence_key
            for slot in today_after.slots
            for card in slot.cards
        ]

        assert schedule_keys == today_keys
