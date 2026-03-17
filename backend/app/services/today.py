"""Today projection and logging for compiled routine cards."""

from __future__ import annotations

from collections import defaultdict

from ..infra.database import (
    load_card_logs,
    save_card_log,
)
from ..models import (
    CardLog,
    ScheduleOccurrence,
    TodayCard,
    TodayCardLogUpdateRequest,
    TodayResponse,
    TodaySlot,
    TodayStats,
)
from .schedule_projection import _SLOT_ORDER, get_schedule_window

_SLOT_LABELS = {
    "morning": "Morning",
    "midday": "Midday",
    "evening": "Evening",
    "anytime": "Anytime",
}


def _today_card_from_occurrence(occurrence: ScheduleOccurrence) -> TodayCard:
    return TodayCard(**occurrence.model_dump())


def _build_scheduled_cards(date: str) -> dict[str, TodayCard]:
    window = get_schedule_window(date, duration_days=1)
    occurrences = window.days[0].occurrences if window.days else []
    return {
        occurrence.occurrence_key: _today_card_from_occurrence(occurrence)
        for occurrence in occurrences
    }


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
