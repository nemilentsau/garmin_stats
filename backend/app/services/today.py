"""Today projection and logging for compiled routine cards."""

from __future__ import annotations

from collections import defaultdict

from ..infra.database import (
    load_card_logs,
    load_card_overrides,
    load_card_template,
    save_card_log,
    save_card_override,
)
from ..models import (
    CardLog,
    CardOverride,
    ScheduleOccurrence,
    TodayCard,
    TodayCardLogUpdateRequest,
    TodayCardOverrideCreateRequest,
    TodayResponse,
    TodaySlot,
    TodayStats,
)
from .schedule_projection import get_schedule_window

_SLOT_ORDER = ("morning", "midday", "evening", "anytime")
_SLOT_LABELS = {
    "morning": "Morning",
    "midday": "Midday",
    "evening": "Evening",
    "anytime": "Anytime",
}


def _override_occurrence_key(override: CardOverride, date: str) -> str:
    return f"override:{override.action}:{override.id}:{date}"


def _today_card_from_occurrence(occurrence: ScheduleOccurrence) -> TodayCard:
    return TodayCard(
        occurrence_key=occurrence.occurrence_key,
        date=occurrence.date,
        slot=occurrence.slot,
        position=occurrence.position,
        source_kind="scheduled",
        routine_id=occurrence.routine_id,
        routine_name=occurrence.routine_name,
        assignment_id=occurrence.assignment_id,
        card_template_id=occurrence.card_template_id,
        name=occurrence.name,
        renderer=occurrence.renderer,
        summary=occurrence.summary,
        tags=occurrence.tags,
        payload_json=occurrence.payload_json,
    )


def _build_scheduled_cards(date: str) -> dict[str, TodayCard]:
    window = get_schedule_window(date, duration_days=1)
    occurrences = window.days[0].occurrences if window.days else []
    return {
        occurrence.occurrence_key: _today_card_from_occurrence(occurrence)
        for occurrence in occurrences
    }


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
        payload_json=dict(template.payload_json),
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
