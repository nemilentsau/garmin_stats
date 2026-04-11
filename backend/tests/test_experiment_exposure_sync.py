"""Tests for experiment exposure sync derived from routine card logs."""

from app.domains.routines.application.today import get_today
from app.domains.routines.infra.sqlite_repository import SqliteRoutineRepository
from app.infra.database import (
    load_experiment_analysis,
    load_experiment_exposures,
    save_card_log,
    save_experiment,
    save_experiment_analysis,
)
from app.models import (
    AssistantArtifactCreateRequest,
    CardLog,
    Experiment,
    ExperimentDesign,
)
from app.services.experiment_analysis import compute_experiment_analysis
from app.services.training_specs import (
    activate_assistant_artifact,
    create_assistant_artifact,
)


def _card_request(card_id: str, *, slot_default: str) -> AssistantArtifactCreateRequest:
    return AssistantArtifactCreateRequest(
        id=f"artifact-{card_id}",
        kind="card_template",
        schema_version=1,
        payload_json={
            "id": card_id,
            "name": f"Card {card_id}",
            "renderer": "timer_session",
            "slot_default": slot_default,
            "summary": "Exposure sync fixture card",
            "tags": ["training"],
            "payload": {
                "duration_minutes": 10,
                "pattern": "5s in / 5s out",
                "instructions": "Stay relaxed.",
            },
        },
    )


def _routine_request(routine_id: str) -> AssistantArtifactCreateRequest:
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
            "notes": "Exposure sync fixture routine",
            "assignments": [
                {
                    "id": f"{routine_id}-morning",
                    "card_template_id": "card-morning",
                    "day": 1,
                    "slot": "morning",
                    "position": 10,
                    "prescription_override_json": {},
                },
                {
                    "id": f"{routine_id}-evening",
                    "card_template_id": "card-evening",
                    "day": 1,
                    "slot": "evening",
                    "position": 10,
                    "prescription_override_json": {},
                },
            ],
        },
    )


def _activate_two_card_routine(routine_id: str) -> None:
    create_assistant_artifact(_card_request("card-morning", slot_default="morning"))
    activate_assistant_artifact("artifact-card-morning")
    create_assistant_artifact(_card_request("card-evening", slot_default="evening"))
    activate_assistant_artifact("artifact-card-evening")
    create_assistant_artifact(_routine_request(routine_id))
    activate_assistant_artifact(f"artifact-{routine_id}")


def _save_linked_experiment(experiment_id: str, routine_id: str) -> None:
    save_experiment(
        Experiment(
            id=experiment_id,
            name="Meditation -> HRV",
            status="draft",
            linked_routine_ids=[routine_id],
        )
    )


def _scheduled_cards_for(date: str):
    repo = SqliteRoutineRepository()
    today = get_today(repo, date=date)
    return [card for slot in today.slots for card in slot.cards]


def test_sync_experiment_exposures_marks_day_full_when_all_linked_cards_completed():
    _activate_two_card_routine("routine-exposure-full")
    _save_linked_experiment("exp-full", "routine-exposure-full")

    scheduled_cards = _scheduled_cards_for("2026-03-02")
    for card in scheduled_cards:
        save_card_log(
            CardLog(
                id=f"card-log:{card.date}:{card.occurrence_key}",
                date=card.date,
                occurrence_key=card.occurrence_key,
                card_template_id=card.card_template_id,
                assignment_id=card.assignment_id,
                status="completed",
                actual_json={},
                notes=None,
            )
        )

    from app.services.experiment_exposure_sync import sync_experiment_exposures_for_date

    sync_experiment_exposures_for_date("2026-03-02")

    exposures = load_experiment_exposures(experiment_id="exp-full")
    assert len(exposures) == 1
    assert exposures[0].date == "2026-03-02"
    assert exposures[0].adherence_state == "full"
    assert exposures[0].exposure_score == 1.0
    assert sorted(exposures[0].linked_routine_entry_ids) == sorted(
        [card.occurrence_key for card in scheduled_cards]
    )


def test_sync_experiment_exposures_marks_day_partial_when_only_part_of_daily_dose_is_done():
    _activate_two_card_routine("routine-exposure-partial")
    _save_linked_experiment("exp-partial", "routine-exposure-partial")

    scheduled_cards = _scheduled_cards_for("2026-03-02")
    first_card = scheduled_cards[0]
    save_card_log(
        CardLog(
            id=f"card-log:{first_card.date}:{first_card.occurrence_key}",
            date=first_card.date,
            occurrence_key=first_card.occurrence_key,
            card_template_id=first_card.card_template_id,
            assignment_id=first_card.assignment_id,
            status="completed",
            actual_json={},
            notes=None,
        )
    )

    from app.services.experiment_exposure_sync import sync_experiment_exposures_for_date

    sync_experiment_exposures_for_date("2026-03-02")

    exposures = load_experiment_exposures(experiment_id="exp-partial")
    assert len(exposures) == 1
    assert exposures[0].adherence_state == "partial"
    assert exposures[0].exposure_score == 0.5


def test_sync_experiment_exposures_refreshes_persisted_analysis_snapshot():
    _activate_two_card_routine("routine-exposure-analysis")
    experiment = Experiment(
        id="exp-analysis-refresh",
        name="Meditation -> HRV",
        status="active",
        linked_routine_ids=["routine-exposure-analysis"],
        design=ExperimentDesign(
            baseline_start_date="2026-02-20",
            baseline_end_date="2026-03-01",
            treatment_start_date="2026-03-02",
            treatment_end_date="2026-03-02",
        ),
    )
    save_experiment(experiment)
    save_experiment_analysis(experiment.id, compute_experiment_analysis(experiment))

    scheduled_cards = _scheduled_cards_for("2026-03-02")
    for card in scheduled_cards:
        save_card_log(
            CardLog(
                id=f"card-log:{card.date}:{card.occurrence_key}",
                date=card.date,
                occurrence_key=card.occurrence_key,
                card_template_id=card.card_template_id,
                assignment_id=card.assignment_id,
                status="completed",
                actual_json={},
                notes=None,
            )
        )

    before = load_experiment_analysis("exp-analysis-refresh")
    assert before is not None
    assert before.adherence_rate == 0.0
    assert before.adherence_by_day[0].state == "unknown"

    from app.services.experiment_exposure_sync import sync_experiment_exposures_for_date

    sync_experiment_exposures_for_date("2026-03-02")

    after = load_experiment_analysis("exp-analysis-refresh")
    assert after is not None
    assert after.adherence_rate == 1.0
    assert after.adherence_by_day[0].state == "full"
