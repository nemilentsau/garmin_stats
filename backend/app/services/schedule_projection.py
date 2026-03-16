"""Shared schedule projection for resolved routine occurrences."""

from __future__ import annotations

from collections import defaultdict
from datetime import date as date_cls
from datetime import timedelta
from typing import cast

from ..infra.database import (
    load_card_overrides,
    load_card_template,
    load_card_templates,
    load_routine_assignments,
    load_routine_schedules,
)
from ..models import (
    CardOverride,
    CardTemplate,
    RoutineAssignment,
    RoutineSchedule,
    ScheduleDay,
    ScheduleOccurrence,
    ScheduleOccurrenceSourceKind,
    ScheduleWindow,
    SlotName,
    WeekdayName,
)

_SLOT_ORDER: tuple[SlotName, ...] = ("morning", "midday", "evening", "anytime")
_WEEKDAY_NAMES: tuple[WeekdayName, ...] = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
_SLOT_INDEX = {slot: index for index, slot in enumerate(_SLOT_ORDER)}


def parse_schedule_date(date_str: str) -> date_cls:
    """Parse an ISO date string for schedule projection."""
    return date_cls.fromisoformat(date_str)


def scheduled_occurrence_key(assignment_id: str, date: str) -> str:
    """Build a stable occurrence key for a scheduled assignment on a date."""
    return f"scheduled:{assignment_id}:{date}"


def override_occurrence_key(override: CardOverride, date: str) -> str:
    """Build a stable occurrence key for a schedule override on a date."""
    return f"override:{override.action}:{override.id}:{date}"


def merge_schedule_payload(
    card: CardTemplate,
    assignment: RoutineAssignment | None,
) -> dict[str, object]:
    """Apply assignment-level prescription overrides onto the card payload."""
    payload = dict(card.payload_json)
    if assignment is not None and assignment.prescription_override_json:
        payload.update(assignment.prescription_override_json)
    return payload


def routine_is_active_on_date(routine: RoutineSchedule, day: date_cls) -> bool:
    """Return whether a routine is active for a specific calendar date."""
    start_date = parse_schedule_date(routine.start_date)
    if day < start_date:
        return False
    if routine.end_date is not None and day > parse_schedule_date(routine.end_date):
        return False
    return routine.status == "active"


def resolve_cycle_week(routine: RoutineSchedule, day: date_cls) -> int:
    """Resolve the recurrence cycle week for a routine on a specific date."""
    if routine.cadence == "weekly":
        return 1
    start_date = parse_schedule_date(routine.start_date)
    weeks_since_start = (day - start_date).days // 7
    return (weeks_since_start % 2) + 1


def assignment_matches_date(
    routine: RoutineSchedule,
    assignment: RoutineAssignment,
    day: date_cls,
) -> bool:
    """Return whether an assignment should occur on a specific date."""
    if assignment.weekday != _WEEKDAY_NAMES[day.weekday()]:
        return False
    return assignment.cycle_week == resolve_cycle_week(routine, day)


def _sort_occurrences_key(occurrence: ScheduleOccurrence) -> tuple[int, int, str]:
    return (_SLOT_INDEX[occurrence.slot], occurrence.position, occurrence.name)


def _base_occurrences_for_day(
    day: date_cls,
    *,
    routines: list[RoutineSchedule],
    card_lookup: dict[str, CardTemplate],
    assignment_lookup: dict[str, list[RoutineAssignment]],
) -> list[ScheduleOccurrence]:
    occurrences: list[ScheduleOccurrence] = []
    date_str = day.isoformat()
    for routine in routines:
        if not routine_is_active_on_date(routine, day):
            continue
        for assignment in assignment_lookup.get(routine.id, []):
            if not assignment_matches_date(routine, assignment, day):
                continue
            card = card_lookup.get(assignment.card_template_id)
            if card is None:
                continue
            occurrences.append(
                ScheduleOccurrence(
                    occurrence_key=scheduled_occurrence_key(assignment.id, date_str),
                    date=date_str,
                    slot=assignment.slot,
                    position=assignment.position,
                    source_kind="scheduled",
                    routine_id=routine.id,
                    routine_name=routine.name,
                    assignment_id=assignment.id,
                    card_template_id=card.id,
                    name=card.name,
                    renderer=card.renderer,
                    summary=card.summary,
                    tags=card.tags,
                    payload_json=merge_schedule_payload(card, assignment),
                )
            )
    return occurrences


def _card_template_for_override(
    override: CardOverride,
    card_lookup: dict[str, CardTemplate],
) -> CardTemplate | None:
    if override.card_template_id is None:
        return None
    template = card_lookup.get(override.card_template_id)
    if template is not None:
        return template
    return load_card_template(override.card_template_id)


def _occurrence_for_override(
    *,
    override: CardOverride,
    date: str,
    card_lookup: dict[str, CardTemplate],
    target_occurrence: ScheduleOccurrence | None,
) -> ScheduleOccurrence | None:
    template = _card_template_for_override(override, card_lookup)
    if template is None:
        return None

    slot = override.slot or (
        target_occurrence.slot if target_occurrence is not None else template.slot_default
    )
    position = (
        override.position
        if override.position is not None
        else (target_occurrence.position if target_occurrence is not None else 999)
    )
    source_kind = cast(
        ScheduleOccurrenceSourceKind,
        f"override_{override.action}",
    )
    return ScheduleOccurrence(
        occurrence_key=override_occurrence_key(override, date),
        date=date,
        slot=slot,
        position=position,
        source_kind=source_kind,
        schedule_override_action=override.action,
        target_occurrence_key=override.target_occurrence_key,
        routine_id=target_occurrence.routine_id if target_occurrence is not None else None,
        routine_name=target_occurrence.routine_name if target_occurrence is not None else None,
        assignment_id=target_occurrence.assignment_id if target_occurrence is not None else None,
        card_template_id=template.id,
        name=template.name,
        renderer=template.renderer,
        summary=template.summary,
        tags=template.tags,
        payload_json=dict(template.payload_json),
    )


def _apply_overrides(
    occurrences: list[ScheduleOccurrence],
    *,
    date: str,
    card_lookup: dict[str, CardTemplate],
) -> list[ScheduleOccurrence]:
    updated = {occurrence.occurrence_key: occurrence for occurrence in occurrences}
    for override in load_card_overrides(date):
        target_occurrence = (
            updated.get(override.target_occurrence_key or "")
            if override.target_occurrence_key is not None
            else None
        )
        if override.action == "hide":
            if override.target_occurrence_key is not None:
                updated.pop(override.target_occurrence_key, None)
            continue
        if override.action == "replace":
            if override.target_occurrence_key is not None:
                updated.pop(override.target_occurrence_key, None)
            occurrence = _occurrence_for_override(
                override=override,
                date=date,
                card_lookup=card_lookup,
                target_occurrence=target_occurrence,
            )
            if occurrence is not None:
                updated[occurrence.occurrence_key] = occurrence
            continue
        occurrence = _occurrence_for_override(
            override=override,
            date=date,
            card_lookup=card_lookup,
            target_occurrence=None,
        )
        if occurrence is not None:
            updated[occurrence.occurrence_key] = occurrence
    return sorted(updated.values(), key=_sort_occurrences_key)


def _build_occurrences_for_day(
    day: date_cls,
    *,
    routines: list[RoutineSchedule],
    card_lookup: dict[str, CardTemplate],
    assignment_lookup: dict[str, list[RoutineAssignment]],
) -> list[ScheduleOccurrence]:
    base_occurrences = _base_occurrences_for_day(
        day,
        routines=routines,
        card_lookup=card_lookup,
        assignment_lookup=assignment_lookup,
    )
    return _apply_overrides(base_occurrences, date=day.isoformat(), card_lookup=card_lookup)


def get_schedule_window(start_date: str, duration_days: int = 14) -> ScheduleWindow:
    """Return the resolved schedule for a contiguous date window."""
    if duration_days <= 0:
        raise ValueError("duration_days must be greater than 0")

    window_start = parse_schedule_date(start_date)
    window_end = window_start + timedelta(days=duration_days - 1)
    routines = load_routine_schedules(status="active")
    card_lookup = {card.id: card for card in load_card_templates(status="active")}
    assignment_lookup: dict[str, list[RoutineAssignment]] = defaultdict(list)
    for assignment in load_routine_assignments():
        assignment_lookup[assignment.routine_id].append(assignment)

    days: list[ScheduleDay] = []
    for offset in range(duration_days):
        current_day = window_start + timedelta(days=offset)
        days.append(
            ScheduleDay(
                date=current_day.isoformat(),
                weekday=_WEEKDAY_NAMES[current_day.weekday()],
                occurrences=_build_occurrences_for_day(
                    current_day,
                    routines=routines,
                    card_lookup=card_lookup,
                    assignment_lookup=assignment_lookup,
                ),
            )
        )

    return ScheduleWindow(
        start_date=window_start.isoformat(),
        end_date=window_end.isoformat(),
        days=days,
    )
