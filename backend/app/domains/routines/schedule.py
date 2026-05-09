"""Pure schedule-domain helpers."""

from __future__ import annotations

from datetime import date as date_cls

from app.domains.routines.contracts import (
    CardOverride,
    CardTemplate,
    RoutineAssignment,
    RoutineSchedule,
    ScheduleOccurrence,
)

SLOT_ORDER = ("morning", "midday", "evening", "anytime")
_SLOT_INDEX = {slot: index for index, slot in enumerate(SLOT_ORDER)}


def parse_schedule_date(date_str: str) -> date_cls:
    return date_cls.fromisoformat(date_str)


def scheduled_occurrence_key(assignment_id: str, date: str) -> str:
    return f"scheduled:{assignment_id}:{date}"


def override_occurrence_key(override: CardOverride, date: str) -> str:
    return f"override:{override.action}:{override.id}:{date}"


def merge_schedule_payload(
    card: CardTemplate,
    assignment: RoutineAssignment | None,
) -> dict[str, object]:
    payload = dict(card.payload_json)
    if assignment is not None and assignment.prescription_override_json:
        payload.update(assignment.prescription_override_json)
    return payload


def routine_is_active_on_date(routine: RoutineSchedule, day: date_cls) -> bool:
    start_date = parse_schedule_date(routine.start_date)
    if day < start_date:
        return False
    if routine.end_date is not None and day > parse_schedule_date(routine.end_date):
        return False
    return routine.status == "active"


def assignment_matches_date(assignment: RoutineAssignment, day: date_cls) -> bool:
    return assignment.date == day.isoformat()


def occurrence_sort_key(occurrence: ScheduleOccurrence) -> tuple[int, int, str]:
    return (_SLOT_INDEX[occurrence.slot], occurrence.position, occurrence.name)
