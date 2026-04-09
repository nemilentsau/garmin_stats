"""Today board use cases for routines."""

from __future__ import annotations

from collections import defaultdict

from app.domains.routines.application.schedule_window import get_schedule_window
from app.domains.routines.domain.schedule import SLOT_ORDER
from app.models import (
    CardLog,
    CardLogRangeResponse,
    CardLogStatusEntry,
    TodayCard,
    TodayCardLogUpdateRequest,
    TodayResponse,
    TodaySlot,
    TodayStats,
)

from .ports import RoutineRepository

_SLOT_LABELS = {
    "morning": "Morning",
    "midday": "Midday",
    "evening": "Evening",
    "anytime": "Anytime",
}


def get_card_log_range(
    repo: RoutineRepository,
    *,
    start_date: str,
    end_date: str,
) -> CardLogRangeResponse:
    logs = repo.list_card_logs_range(start_date=start_date, end_date=end_date)
    entries = [
        CardLogStatusEntry(occurrence_key=log.occurrence_key, status=log.status)
        for log in logs
        if log.status != "pending"
    ]
    return CardLogRangeResponse(start_date=start_date, end_date=end_date, entries=entries)


def get_today(repo: RoutineRepository, *, date: str) -> TodayResponse:
    window = get_schedule_window(repo, start_date=date, duration_days=1)
    occurrences = window.days[0].occurrences if window.days else []
    cards = {
        occurrence.occurrence_key: TodayCard(**occurrence.model_dump())
        for occurrence in occurrences
    }

    logs_by_occurrence = {log.occurrence_key: log for log in repo.list_card_logs(date=date)}
    for occurrence_key, card in cards.items():
        log = logs_by_occurrence.get(occurrence_key)
        if log is None:
            continue
        card.status = log.status
        card.actual_json = log.actual_json
        card.notes = log.notes

    grouped: dict[str, list[TodayCard]] = defaultdict(list)
    for card in cards.values():
        grouped[card.slot].append(card)

    slots: list[TodaySlot] = []
    stats = TodayStats()
    for slot in SLOT_ORDER:
        slot_cards = sorted(grouped.get(slot, []), key=lambda card: (card.position, card.name))
        slots.append(TodaySlot(slot=slot, label=_SLOT_LABELS[slot], cards=slot_cards))
        for card in slot_cards:
            stats.total += 1
            if card.status == "completed":
                stats.completed += 1
            elif card.status == "partial":
                stats.partial += 1
            elif card.status == "skipped":
                stats.skipped += 1
            else:
                stats.pending += 1

    return TodayResponse(date=date, stats=stats, slots=slots)


def upsert_today_card_log(
    repo: RoutineRepository,
    *,
    date: str,
    occurrence_key: str,
    request: TodayCardLogUpdateRequest,
) -> CardLog:
    scheduled_cards = {
        card.occurrence_key: card
        for slot in get_today(repo, date=date).slots
        for card in slot.cards
    }
    scheduled_card = scheduled_cards.get(occurrence_key)
    if scheduled_card is None:
        raise LookupError(f"Today occurrence {occurrence_key} not found for {date}")
    if request.card_template_id != scheduled_card.card_template_id:
        raise ValueError("Card template does not match the scheduled occurrence")
    if (
        request.assignment_id is not None
        and request.assignment_id != scheduled_card.assignment_id
    ):
        raise ValueError("Assignment id does not match the scheduled occurrence")

    log = CardLog(
        id=f"card-log:{date}:{occurrence_key}",
        date=date,
        occurrence_key=occurrence_key,
        card_template_id=scheduled_card.card_template_id,
        assignment_id=scheduled_card.assignment_id,
        status=request.status,
        actual_json=request.actual_json,
        notes=request.notes,
    )
    repo.save_card_log(log)
    return log
