"""Pydantic contracts owned by the routines domain.

These models describe the compiled live runtime: card templates, routine
schedules, dated occurrences, Today-board responses, and card logs. Draft
artifact specs are owned by the artifacts domain.
"""

from __future__ import annotations

from typing import Literal

from app.contracts.base import (
    AutoTotalResponse,
    DefaultsRequired,
    EntityStatus,
    StrictDefaultsRequired,
)

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


class CardTemplate(DefaultsRequired):
    """Live reusable routine card template."""

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
    """List response for live routine card templates."""

    cards: list[CardTemplate] = []


class RoutineSchedule(DefaultsRequired):
    """Live routine schedule metadata."""

    id: str
    name: str
    status: EntityStatus = "active"
    start_date: str
    end_date: str | None = None
    tags: list[str] = []
    notes: str | None = None
    source_artifact_id: str | None = None


class RoutineAssignment(DefaultsRequired):
    """Dated card assignment compiled from an active routine schedule."""

    id: str
    routine_id: str
    card_template_id: str
    date: str
    slot: SlotName
    position: int = 0
    prescription_override_json: dict[str, object] = {}


class RoutineActivationAssignment(StrictDefaultsRequired):
    """Relative-day card assignment accepted by routine activation."""

    id: str
    card_template_id: str
    day: int
    slot: SlotName
    position: int = 0
    prescription_override_json: dict[str, object] = {}


class RoutineActivationCommand(DefaultsRequired):
    """Command for compiling a routine spec into live dated assignments."""

    id: str
    name: str
    status: EntityStatus = "active"
    start_date: str
    end_date: str | None = None
    tags: list[str] = []
    notes: str | None = None
    source_artifact_id: str | None = None
    assignments: list[RoutineActivationAssignment] = []


class RoutineSchedulesResponse(AutoTotalResponse, items_field="routines"):
    """List response for live routine schedules."""

    routines: list[RoutineSchedule] = []


class RoutineAssignmentsResponse(AutoTotalResponse, items_field="assignments"):
    """List response for live routine assignments."""

    assignments: list[RoutineAssignment] = []


class CardLog(DefaultsRequired):
    """User completion log for one dated card occurrence."""

    id: str
    date: str
    occurrence_key: str
    card_template_id: str
    assignment_id: str | None = None
    status: CardLogStatus = "pending"
    actual_json: dict[str, object] = {}
    notes: str | None = None


class CardOverride(DefaultsRequired):
    """Dated add/hide/replace override for routine card occurrences."""

    id: str
    date: str
    action: CardOverrideAction
    target_occurrence_key: str | None = None
    card_template_id: str | None = None
    slot: SlotName | None = None
    position: int | None = None
    notes: str | None = None


class TodayCardLogUpdateRequest(StrictDefaultsRequired):
    """Request body for updating a Today-board card log."""

    card_template_id: str
    assignment_id: str | None = None
    status: CardLogStatus = "completed"
    actual_json: dict[str, object] = {}
    notes: str | None = None


class TodayStats(DefaultsRequired):
    """Completion counts for a Today-board response."""

    total: int = 0
    completed: int = 0
    partial: int = 0
    skipped: int = 0
    pending: int = 0


class ScheduleOccurrence(DefaultsRequired):
    """Resolved scheduled or override-created card occurrence."""

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


class TodayCard(ScheduleOccurrence):
    """Resolved Today-board card occurrence with log state attached."""

    status: CardLogStatus = "pending"
    actual_json: dict[str, object] = {}
    notes: str | None = None


class TodaySlot(DefaultsRequired):
    """One named Today-board slot containing resolved cards."""

    slot: SlotName
    label: str
    cards: list[TodayCard] = []


class TodayResponse(DefaultsRequired):
    """Today-board response for one local date."""

    date: str
    stats: TodayStats
    slots: list[TodaySlot] = []


class CardLogStatusEntry(DefaultsRequired):
    """Compact card-log status entry for schedule overlays."""

    occurrence_key: str
    status: CardLogStatus


class CardLogRangeResponse(DefaultsRequired):
    """Card-log statuses for a date range."""

    start_date: str
    end_date: str
    entries: list[CardLogStatusEntry] = []


class ScheduleDay(DefaultsRequired):
    """Resolved routine occurrences for one calendar day."""

    date: str
    weekday: WeekdayName
    occurrences: list[ScheduleOccurrence] = []


class ScheduleWindow(DefaultsRequired):
    """Resolved routine schedule window."""

    start_date: str
    end_date: str
    days: list[ScheduleDay] = []
