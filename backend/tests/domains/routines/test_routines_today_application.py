"""Tests for routines today use cases."""

import pytest

from app.domains.experiments.adapters import SqliteExperimentRepository
from app.domains.experiments.contracts import Experiment
from app.domains.routines.adapters import SqliteRoutineRepository
from app.domains.routines.application.today import (
    get_card_log_range,
    get_today,
)
from app.domains.routines.application.today import (
    upsert_today_card_log as _upsert_today_card_log,
)
from app.domains.routines.contracts import (
    CardLog,
    TodayCardLogUpdateRequest,
)
from tests._routines_helpers import (
    activate_routine_card,
    activate_routine_spec,
    routine_assignment_spec,
    upsert_today_card_log,
)


def test_get_today_returns_grouped_slots_and_stats():
    activate_routine_card("card-today")
    activate_routine_spec(
        "routine-today",
        assignments=[
            routine_assignment_spec(
                "routine-today-assignment",
                card_template_id="card-today",
                slot="evening",
                position=20,
            )
        ],
    )

    repo = SqliteRoutineRepository()
    response = get_today(repo, date="2026-03-02")

    assert response.date == "2026-03-02"
    assert response.stats.total == 1
    assert response.slots[2].cards[0].card_template_id == "card-today"


def test_get_card_log_range_excludes_pending_entries():
    repo = SqliteRoutineRepository()
    repo.save_card_log(
        CardLog(
            id="card-log:2026-03-02:pending",
            date="2026-03-02",
            occurrence_key="scheduled:pending:2026-03-02",
            card_template_id="card-pending",
            assignment_id="assignment-pending",
            status="pending",
            actual_json=None,
            notes=None,
        )
    )
    repo.save_card_log(
        CardLog(
            id="card-log:2026-03-02:completed",
            date="2026-03-02",
            occurrence_key="scheduled:completed:2026-03-02",
            card_template_id="card-completed",
            assignment_id="assignment-completed",
            status="completed",
            actual_json=None,
            notes="Done",
        )
    )

    response = get_card_log_range(repo, start_date="2026-03-02", end_date="2026-03-02")

    assert len(response.entries) == 1
    assert response.entries[0].occurrence_key == "scheduled:completed:2026-03-02"
    assert response.entries[0].status == "completed"


def test_upsert_today_card_log_validates_occurrence_identity():
    repo = SqliteRoutineRepository()
    request = TodayCardLogUpdateRequest(
        card_template_id="wrong-card",
        assignment_id=None,
        status="completed",
        actual_json=None,
        notes=None,
    )

    with pytest.raises(LookupError, match="Today occurrence missing not found"):
        _upsert_today_card_log(
            repo, date="2026-03-02", occurrence_key="missing", request=request
        )


def test_upsert_today_card_log_rejects_assignment_mismatch():
    activate_routine_card("card-assignment")
    activate_routine_spec(
        "routine-assignment",
        assignments=[
            routine_assignment_spec(
                "routine-assignment-assignment",
                card_template_id="card-assignment",
                slot="evening",
                position=20,
            )
        ],
    )

    repo = SqliteRoutineRepository()
    today = get_today(repo, date="2026-03-02")
    scheduled_card = today.slots[2].cards[0]

    with pytest.raises(ValueError, match="Assignment id does not match"):
        _upsert_today_card_log(
            repo,
            date="2026-03-02",
            occurrence_key=scheduled_card.occurrence_key,
            request=TodayCardLogUpdateRequest(
                card_template_id=scheduled_card.card_template_id,
                assignment_id="wrong-assignment",
                status="completed",
                actual_json=None,
                notes=None,
            ),
        )


def test_today_card_logs_recompute_linked_experiment_exposure_for_the_day():
    activate_routine_card("card-morning")
    activate_routine_card("card-evening")
    activate_routine_spec(
        "routine-exposure",
        assignments=[
            routine_assignment_spec(
                "routine-exposure-morning",
                card_template_id="card-morning",
                slot="morning",
            ),
            routine_assignment_spec(
                "routine-exposure-evening",
                card_template_id="card-evening",
                slot="evening",
            ),
        ],
    )
    experiment_repo = SqliteExperimentRepository()
    experiment_repo.save_experiment(
        Experiment(
            id="exp-today-sync",
            name="Meditation -> HRV",
            status="draft",
            linked_routine_ids=["routine-exposure"],
        )
    )

    repo = SqliteRoutineRepository()
    today = get_today(repo, date="2026-03-02")
    cards = [card for slot in today.slots for card in slot.cards]
    first_card, second_card = cards

    upsert_today_card_log(
        "2026-03-02",
        first_card.occurrence_key,
        TodayCardLogUpdateRequest(
            card_template_id=first_card.card_template_id,
            assignment_id=first_card.assignment_id,
            status="completed",
            actual_json=None,
            notes=None,
        ),
    )

    exposures = experiment_repo.list_experiment_exposures(experiment_id="exp-today-sync")
    assert len(exposures) == 1
    assert exposures[0].adherence_state == "partial"
    assert exposures[0].exposure_score == 0.5

    upsert_today_card_log(
        "2026-03-02",
        second_card.occurrence_key,
        TodayCardLogUpdateRequest(
            card_template_id=second_card.card_template_id,
            assignment_id=second_card.assignment_id,
            status="completed",
            actual_json=None,
            notes=None,
        ),
    )

    exposures = experiment_repo.list_experiment_exposures(experiment_id="exp-today-sync")
    assert len(exposures) == 1
    assert exposures[0].adherence_state == "full"
    assert exposures[0].exposure_score == 1.0

    upsert_today_card_log(
        "2026-03-02",
        first_card.occurrence_key,
        TodayCardLogUpdateRequest(
            card_template_id=first_card.card_template_id,
            assignment_id=first_card.assignment_id,
            status="skipped",
            actual_json=None,
            notes=None,
        ),
    )

    exposures = experiment_repo.list_experiment_exposures(experiment_id="exp-today-sync")
    assert len(exposures) == 1
    assert exposures[0].adherence_state == "partial"
    assert exposures[0].exposure_score == 0.5
