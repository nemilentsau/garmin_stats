"""Schedule projection use case for routines."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import cast

from app.domains.routines.contracts import (
    CardOverride,
    CardOverrideAction,
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
from app.domains.routines.dependencies import RoutineRepository
from app.domains.routines.schedule import (
    assignment_matches_date,
    merge_schedule_payload,
    occurrence_sort_key,
    override_occurrence_key,
    parse_schedule_date,
    routine_is_active_on_date,
    scheduled_occurrence_key,
)

_WEEKDAY_NAMES: tuple[WeekdayName, ...] = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


def _schedule_occurrence_from_template(
    *,
    occurrence_key: str,
    date: str,
    card: CardTemplate,
    slot: SlotName,
    position: int,
    source_kind: ScheduleOccurrenceSourceKind,
    routine_id: str | None = None,
    routine_name: str | None = None,
    assignment_id: str | None = None,
    schedule_override_action: CardOverrideAction | None = None,
    target_occurrence_key: str | None = None,
    payload_json: dict[str, object] | None = None,
) -> ScheduleOccurrence:
    return ScheduleOccurrence(
        occurrence_key=occurrence_key,
        date=date,
        slot=slot,
        position=position,
        source_kind=source_kind,
        schedule_override_action=schedule_override_action,
        target_occurrence_key=target_occurrence_key,
        routine_id=routine_id,
        routine_name=routine_name,
        assignment_id=assignment_id,
        card_template_id=card.id,
        name=card.name,
        renderer=card.renderer,
        summary=card.summary,
        tags=card.tags,
        payload_json=payload_json if payload_json is not None else dict(card.payload_json),
    )


def _base_occurrences_for_day(
    day: date,
    *,
    routines: list[RoutineSchedule],
    card_lookup: dict[str, CardTemplate],
    assignments_by_routine: dict[str, list[RoutineAssignment]],
) -> list[ScheduleOccurrence]:
    occurrences: list[ScheduleOccurrence] = []
    date_str = day.isoformat()
    for routine in routines:
        if not routine_is_active_on_date(routine, day):
            continue
        for assignment in assignments_by_routine.get(routine.id, []):
            if not assignment_matches_date(assignment, day):
                continue
            card = card_lookup.get(assignment.card_template_id)
            if card is None:
                continue
            occurrences.append(
                _schedule_occurrence_from_template(
                    occurrence_key=scheduled_occurrence_key(assignment.id, date_str),
                    date=date_str,
                    card=card,
                    slot=assignment.slot,
                    position=assignment.position,
                    source_kind="scheduled",
                    routine_id=routine.id,
                    routine_name=routine.name,
                    assignment_id=assignment.id,
                    payload_json=merge_schedule_payload(card, assignment),
                )
            )
    return occurrences


def _apply_overrides(
    repo: RoutineRepository,
    occurrences: list[ScheduleOccurrence],
    *,
    date: str,
    card_lookup: dict[str, CardTemplate],
    overrides: list[CardOverride],
) -> list[ScheduleOccurrence]:
    updated = {occurrence.occurrence_key: occurrence for occurrence in occurrences}
    for override in overrides:
        target_occurrence = (
            updated.get(override.target_occurrence_key or "")
            if override.target_occurrence_key is not None
            else None
        )
        if override.action == "hide":
            if override.target_occurrence_key is not None:
                updated.pop(override.target_occurrence_key, None)
            continue
        if override.action == "replace" and (
            override.target_occurrence_key is None or target_occurrence is None
        ):
            continue
        if override.card_template_id is None:
            continue
        template = card_lookup.get(override.card_template_id)
        if template is None:
            template = repo.get_card_template(override.card_template_id)
            if template is not None:
                card_lookup[override.card_template_id] = template
        if template is None:
            continue

        slot = override.slot or (
            target_occurrence.slot if target_occurrence is not None else template.slot_default
        )
        position = (
            override.position
            if override.position is not None
            else (target_occurrence.position if target_occurrence is not None else 999)
        )
        source_kind = cast(ScheduleOccurrenceSourceKind, f"override_{override.action}")
        occurrence = _schedule_occurrence_from_template(
            occurrence_key=override_occurrence_key(override, date),
            date=date,
            card=template,
            slot=slot,
            position=position,
            source_kind=source_kind,
            schedule_override_action=override.action,
            target_occurrence_key=override.target_occurrence_key,
            routine_id=target_occurrence.routine_id if target_occurrence is not None else None,
            routine_name=target_occurrence.routine_name if target_occurrence is not None else None,
            assignment_id=(
                target_occurrence.assignment_id if target_occurrence is not None else None
            ),
            payload_json=dict(template.payload_json),
        )
        if override.action == "replace" and override.target_occurrence_key is not None:
            updated.pop(override.target_occurrence_key, None)
        updated[occurrence.occurrence_key] = occurrence
    return sorted(updated.values(), key=occurrence_sort_key)


def get_schedule_window(
    repo: RoutineRepository,
    *,
    start_date: str,
    duration_days: int = 14,
) -> ScheduleWindow:
    if duration_days <= 0:
        raise ValueError("duration_days must be greater than 0")

    window_start = parse_schedule_date(start_date)
    window_end = window_start + timedelta(days=duration_days - 1)
    routines = repo.list_routines(status="active")
    assignments = repo.list_assignments()
    card_lookup = {card.id: card for card in repo.list_card_templates(status="active")}
    assignments_by_routine: dict[str, list[RoutineAssignment]] = defaultdict(list)
    for assignment in assignments:
        assignments_by_routine[assignment.routine_id].append(assignment)

    overrides_by_date: dict[str, list[CardOverride]] = defaultdict(list)
    for override in repo.list_card_overrides_range(
        start_date=start_date,
        end_date=window_end.isoformat(),
    ):
        overrides_by_date[override.date].append(override)

    days: list[ScheduleDay] = []
    for offset in range(duration_days):
        day = window_start + timedelta(days=offset)
        date_str = day.isoformat()
        base_occurrences = _base_occurrences_for_day(
            day,
            routines=routines,
            card_lookup=card_lookup,
            assignments_by_routine=assignments_by_routine,
        )
        occurrences = _apply_overrides(
            repo,
            base_occurrences,
            date=date_str,
            card_lookup=card_lookup,
            overrides=overrides_by_date.get(date_str, []),
        )
        days.append(
            ScheduleDay(
                date=date_str,
                weekday=_WEEKDAY_NAMES[day.weekday()],
                occurrences=occurrences,
            )
        )

    return ScheduleWindow(start_date=start_date, end_date=window_end.isoformat(), days=days)
