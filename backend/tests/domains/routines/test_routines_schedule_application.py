"""Routines schedule-window application tests."""

import pytest

from app.domains.routines.adapters import SqliteRoutineRepository
from app.domains.routines.application.schedule_window import get_schedule_window
from app.domains.routines.contracts import CardOverride
from app.infra.database import save_card_override
from tests._routines_helpers import (
    activate_routine_card as _activate_card,
)
from tests._routines_helpers import (
    activate_routine_spec,
    routine_assignment_spec,
)


def _activate_routine(routine_id: str, *, card_id: str) -> None:
    activate_routine_spec(
        routine_id,
        assignments=[
            routine_assignment_spec(
                f"{routine_id}-morning-late",
                card_template_id=card_id,
                slot="morning",
                position=30,
            )
        ],
    )


def test_schedule_window_returns_sorted_occurrences():
    _activate_card("card-schedule")
    _activate_routine("routine-schedule", card_id="card-schedule")

    repo = SqliteRoutineRepository()
    window = get_schedule_window(repo, start_date="2026-03-02", duration_days=1)

    assert window.start_date == "2026-03-02"
    assert window.end_date == "2026-03-02"
    assert [occurrence.card_template_id for occurrence in window.days[0].occurrences] == [
        "card-schedule"
    ]


def test_schedule_window_applies_persisted_overrides():
    _activate_card("card-main")
    _activate_card("card-extra")
    _activate_routine("routine-main", card_id="card-main")

    repo = SqliteRoutineRepository()
    baseline = get_schedule_window(repo, start_date="2026-03-02", duration_days=1)
    scheduled_occurrence = baseline.days[0].occurrences[0]
    save_card_override(
        CardOverride(
            id="override-extra",
            date="2026-03-02",
            action="replace",
            target_occurrence_key=scheduled_occurrence.occurrence_key,
            card_template_id="card-extra",
        )
    )
    window = get_schedule_window(repo, start_date="2026-03-02", duration_days=1)

    assert [occurrence.card_template_id for occurrence in window.days[0].occurrences] == [
        "card-extra"
    ]


def test_schedule_window_rejects_non_positive_duration():
    repo = SqliteRoutineRepository()

    with pytest.raises(ValueError, match="duration_days must be greater than 0"):
        get_schedule_window(repo, start_date="2026-03-02", duration_days=0)
