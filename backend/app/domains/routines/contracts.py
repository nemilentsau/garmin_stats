"""API and persistence contracts for the live routine runtime."""

from __future__ import annotations

from typing import Literal

from app.contracts.base import (
    AutoTotalResponse,
    DefaultsRequired,
    EntityStatus,
    StrictDefaultsRequired,
)

RoutineEntryCompletionState = Literal["completed", "partial", "skipped"]
RendererFamily = Literal["timer_session", "checklist_block", "exercise_block"]
SlotName = Literal["morning", "midday", "evening", "anytime"]
WeekdayName = Literal[
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]
CardLogStatus = Literal["pending", "completed", "partial", "skipped"]
CardOverrideAction = Literal["add", "hide", "replace"]
ScheduleOccurrenceSourceKind = Literal["scheduled", "override_add", "override_replace"]


class Routine(DefaultsRequired):
    id: str
    name: str
    category: str
    status: EntityStatus = "active"
    description: str | None = None
    default_unit: str = "boolean"
    target_frequency: str | None = None
    default_time_of_day: str | None = None
    tags: list[str] = []
    linked_goal_ids: list[str] = []


class RoutineEntry(DefaultsRequired):
    id: str
    routine_id: str
    date: str
    timestamp_local: str | None = None
    value_numeric: float | None = None
    value_text: str | None = None
    completion_state: RoutineEntryCompletionState = "completed"
    source: str = "manual"
    notes: str | None = None


class RoutinesResponse(AutoTotalResponse, items_field="routines"):
    routines: list[Routine] = []
    total: int = 0


class RoutineEntriesResponse(AutoTotalResponse, items_field="entries"):
    entries: list[RoutineEntry] = []
    total: int = 0


class CardTemplate(DefaultsRequired):
    id: str
    name: str
    renderer: RendererFamily
    slot_default: SlotName
    status: EntityStatus = "active"
    summary: str | None = None
    tags: list[str] = []
    payload_json: dict[str, object] = {}
    source_artifact_id: str | None = None


class CardTemplatesResponse(AutoTotalResponse, items_field="cards"):
    cards: list[CardTemplate] = []
    total: int = 0


class RoutineSchedule(DefaultsRequired):
    id: str
    name: str
    status: EntityStatus = "active"
    start_date: str
    end_date: str | None = None
    tags: list[str] = []
    notes: str | None = None
    source_artifact_id: str | None = None


class RoutineAssignment(DefaultsRequired):
    id: str
    routine_id: str
    card_template_id: str
    date: str
    slot: SlotName
    position: int = 0
    prescription_override_json: dict[str, object] = {}


class RoutineSchedulesResponse(AutoTotalResponse, items_field="routines"):
    routines: list[RoutineSchedule] = []
    total: int = 0


class RoutineAssignmentsResponse(AutoTotalResponse, items_field="assignments"):
    assignments: list[RoutineAssignment] = []
    total: int = 0


class CardLog(DefaultsRequired):
    id: str
    date: str
    occurrence_key: str
    card_template_id: str
    assignment_id: str | None = None
    status: CardLogStatus = "pending"
    actual_json: dict[str, object] = {}
    notes: str | None = None


class CardOverride(DefaultsRequired):
    id: str
    date: str
    action: CardOverrideAction
    target_occurrence_key: str | None = None
    card_template_id: str | None = None
    slot: SlotName | None = None
    position: int | None = None
    notes: str | None = None


class TodayCardLogUpdateRequest(StrictDefaultsRequired):
    card_template_id: str
    assignment_id: str | None = None
    status: CardLogStatus = "completed"
    actual_json: dict[str, object] = {}
    notes: str | None = None


class TodayStats(DefaultsRequired):
    total: int = 0
    completed: int = 0
    partial: int = 0
    skipped: int = 0
    pending: int = 0


class TodayCard(DefaultsRequired):
    occurrence_key: str
    date: str
    slot: SlotName
    position: int = 0
    source_kind: ScheduleOccurrenceSourceKind
    schedule_override_action: CardOverrideAction | None = None
    target_occurrence_key: str | None = None
    routine_id: str | None = None
    routine_name: str | None = None
    assignment_id: str | None = None
    card_template_id: str
    name: str
    renderer: RendererFamily
    summary: str | None = None
    tags: list[str] = []
    payload_json: dict[str, object] = {}
    status: CardLogStatus = "pending"
    actual_json: dict[str, object] = {}
    notes: str | None = None


class TodaySlot(DefaultsRequired):
    slot: SlotName
    label: str
    cards: list[TodayCard] = []


class TodayResponse(DefaultsRequired):
    date: str
    stats: TodayStats
    slots: list[TodaySlot] = []


class CardLogStatusEntry(DefaultsRequired):
    occurrence_key: str
    status: CardLogStatus


class CardLogRangeResponse(DefaultsRequired):
    start_date: str
    end_date: str
    entries: list[CardLogStatusEntry] = []


class ScheduleOccurrence(DefaultsRequired):
    occurrence_key: str
    date: str
    slot: SlotName
    position: int = 0
    source_kind: ScheduleOccurrenceSourceKind = "scheduled"
    schedule_override_action: CardOverrideAction | None = None
    target_occurrence_key: str | None = None
    routine_id: str | None = None
    routine_name: str | None = None
    assignment_id: str | None = None
    card_template_id: str
    name: str
    renderer: RendererFamily
    summary: str | None = None
    tags: list[str] = []
    payload_json: dict[str, object] = {}


class ScheduleDay(DefaultsRequired):
    date: str
    weekday: WeekdayName
    occurrences: list[ScheduleOccurrence] = []


class ScheduleWindow(DefaultsRequired):
    start_date: str
    end_date: str
    days: list[ScheduleDay] = []
