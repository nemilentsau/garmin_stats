"""Today projection and logging for compiled routine cards."""

from __future__ import annotations

from collections import defaultdict
from datetime import date as date_cls

from ..infra.database import (
    load_card_logs,
    load_card_overrides,
    load_card_template,
    load_card_templates,
    load_routine_assignments,
    load_routine_schedules,
    save_card_log,
    save_card_override,
)
from ..models import (
    CardLog,
    CardOverride,
    CardTemplate,
    RoutineAssignment,
    RoutineSchedule,
    SlotName,
    TodayCard,
    TodayCardLogUpdateRequest,
    TodayCardOverrideCreateRequest,
    TodayResponse,
    TodaySlot,
    TodayStats,
)

_SLOT_ORDER: tuple[SlotName, ...] = ("morning", "midday", "evening", "anytime")
_SLOT_LABELS = {
    "morning": "Morning",
    "midday": "Midday",
    "evening": "Evening",
    "anytime": "Anytime",
}
_WEEKDAY_NAMES = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


def _parse_date(date_str: str) -> date_cls:
    return date_cls.fromisoformat(date_str)


def _routine_is_active_on_date(routine: RoutineSchedule, day: date_cls) -> bool:
    start_date = _parse_date(routine.start_date)
    if day < start_date:
        return False
    if routine.end_date is not None and day > _parse_date(routine.end_date):
        return False
    return routine.status == "active"


def _resolve_cycle_week(routine: RoutineSchedule, day: date_cls) -> int:
    if routine.cadence == "weekly":
        return 1
    start_date = _parse_date(routine.start_date)
    weeks_since_start = (day - start_date).days // 7
    return (weeks_since_start % 2) + 1


def _assignment_matches_date(
    routine: RoutineSchedule,
    assignment: RoutineAssignment,
    day: date_cls,
) -> bool:
    if assignment.weekday != _WEEKDAY_NAMES[day.weekday()]:
        return False
    return assignment.cycle_week == _resolve_cycle_week(routine, day)


def _merge_payload(
    card: CardTemplate,
    assignment: RoutineAssignment | None,
) -> dict[str, object]:
    payload = dict(card.payload_json)
    if assignment is not None and assignment.prescription_override_json:
        payload.update(assignment.prescription_override_json)
    return payload


def _scheduled_occurrence_key(assignment_id: str, date: str) -> str:
    return f"scheduled:{assignment_id}:{date}"


def _override_occurrence_key(override: CardOverride, date: str) -> str:
    return f"override:{override.action}:{override.id}:{date}"


def _build_scheduled_cards(date: str) -> dict[str, TodayCard]:
    target_day = _parse_date(date)
    card_lookup = {card.id: card for card in load_card_templates(status="active")}
    assignment_lookup: dict[str, list[RoutineAssignment]] = defaultdict(list)
    for assignment in load_routine_assignments():
        assignment_lookup[assignment.routine_id].append(assignment)

    cards: dict[str, TodayCard] = {}
    for routine in load_routine_schedules(status="active"):
        if not _routine_is_active_on_date(routine, target_day):
            continue
        for assignment in assignment_lookup.get(routine.id, []):
            if not _assignment_matches_date(routine, assignment, target_day):
                continue
            card = card_lookup.get(assignment.card_template_id)
            if card is None:
                continue
            occurrence_key = _scheduled_occurrence_key(assignment.id, date)
            cards[occurrence_key] = TodayCard(
                occurrence_key=occurrence_key,
                date=date,
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
                payload_json=_merge_payload(card, assignment),
            )
    return cards


def _card_for_override(
    *,
    override: CardOverride,
    date: str,
    target_card: TodayCard | None,
) -> TodayCard | None:
    if override.card_template_id is None:
        return None
    template = load_card_template(override.card_template_id)
    if template is None:
        return None
    slot = override.slot or (target_card.slot if target_card is not None else template.slot_default)
    position = (
        override.position
        if override.position is not None
        else (target_card.position if target_card is not None else 999)
    )
    return TodayCard(
        occurrence_key=_override_occurrence_key(override, date),
        date=date,
        slot=slot,
        position=position,
        source_kind=f"override_{override.action}",
        routine_id=target_card.routine_id if target_card is not None else None,
        routine_name=target_card.routine_name if target_card is not None else None,
        assignment_id=target_card.assignment_id if target_card is not None else None,
        card_template_id=template.id,
        name=template.name,
        renderer=template.renderer,
        summary=template.summary,
        tags=template.tags,
        payload_json=_merge_payload(template, None),
    )


def _apply_overrides(cards: dict[str, TodayCard], date: str) -> dict[str, TodayCard]:
    updated = dict(cards)
    for override in load_card_overrides(date):
        target_card = (
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
            override_card = _card_for_override(
                override=override,
                date=date,
                target_card=target_card,
            )
            if override_card is not None:
                updated[override_card.occurrence_key] = override_card
            continue
        override_card = _card_for_override(override=override, date=date, target_card=None)
        if override_card is not None:
            updated[override_card.occurrence_key] = override_card
    return updated


def _apply_logs(cards: dict[str, TodayCard], date: str) -> None:
    logs_by_occurrence = {log.occurrence_key: log for log in load_card_logs(date)}
    for occurrence_key, card in cards.items():
        log = logs_by_occurrence.get(occurrence_key)
        if log is None:
            continue
        card.status = log.status
        card.actual_json = log.actual_json
        card.notes = log.notes


def _group_slots(cards: dict[str, TodayCard]) -> list[TodaySlot]:
    grouped: dict[str, list[TodayCard]] = defaultdict(list)
    for card in cards.values():
        grouped[card.slot].append(card)

    slots: list[TodaySlot] = []
    for slot in _SLOT_ORDER:
        slot_cards = sorted(grouped.get(slot, []), key=lambda card: (card.position, card.name))
        slots.append(TodaySlot(slot=slot, label=_SLOT_LABELS[slot], cards=slot_cards))
    return slots


def _build_stats(slots: list[TodaySlot]) -> TodayStats:
    stats = TodayStats()
    for slot in slots:
        for card in slot.cards:
            stats.total += 1
            if card.status == "completed":
                stats.completed += 1
            elif card.status == "partial":
                stats.partial += 1
            elif card.status == "skipped":
                stats.skipped += 1
            else:
                stats.pending += 1
    return stats


def get_today(date: str) -> TodayResponse:
    cards = _build_scheduled_cards(date)
    cards = _apply_overrides(cards, date)
    _apply_logs(cards, date)
    slots = _group_slots(cards)
    return TodayResponse(date=date, stats=_build_stats(slots), slots=slots)


def upsert_today_card_log(
    date: str,
    occurrence_key: str,
    request: TodayCardLogUpdateRequest,
) -> CardLog:
    log = CardLog(
        id=f"card-log:{date}:{occurrence_key}",
        date=date,
        occurrence_key=occurrence_key,
        card_template_id=request.card_template_id,
        assignment_id=request.assignment_id,
        status=request.status,
        actual_json=request.actual_json,
        notes=request.notes,
    )
    save_card_log(log)
    return log


def create_today_override(date: str, request: TodayCardOverrideCreateRequest) -> CardOverride:
    if request.action in {"add", "replace"} and request.card_template_id is None:
        raise ValueError("card_template_id is required for add/replace overrides")
    if request.action in {"hide", "replace"} and request.target_occurrence_key is None:
        raise ValueError("target_occurrence_key is required for hide/replace overrides")
    if (
        request.card_template_id is not None
        and load_card_template(request.card_template_id) is None
    ):
        raise LookupError(f"Card template {request.card_template_id} not found")

    override = CardOverride(
        id=request.id,
        date=date,
        action=request.action,
        target_occurrence_key=request.target_occurrence_key,
        card_template_id=request.card_template_id,
        slot=request.slot,
        position=request.position,
        notes=request.notes,
    )
    save_card_override(override)
    return override


def hide_today_card(date: str, occurrence_key: str) -> CardOverride:
    override = CardOverride(
        id=f"hide-{date}-{occurrence_key}",
        date=date,
        action="hide",
        target_occurrence_key=occurrence_key,
    )
    save_card_override(override)
    return override
