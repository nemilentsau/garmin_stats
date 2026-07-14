"""Pure read-time activation of authored measurement backup opportunities.

The imported block and compiled schedule remain the source of truth. This
module only overlays one requested day: when an authored backup is due and no
earlier attempt is valid, it relocates the original measurement occurrence
into an existing ``running.v3`` slot. It never creates a slot, edits an
artifact, or persists the resolved view.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from app.domains.training.application.compile import CompiledEntry, is_running_bundle
from app.domains.training.contracts import (
    MeasurementStatus,
    TrainingRequiredAction,
    V3Block,
)

AttemptStatuses = Mapping[str, Mapping[int, MeasurementStatus]]


@dataclass(frozen=True)
class MeasurementBackupActivation:
    """One event's explicit ownership of an entry in the resolved day."""

    event_id: str
    entry_index: int


@dataclass(frozen=True)
class MeasurementDayResolution:
    """Immutable schedule overlay and event state for one block day."""

    entries: tuple[CompiledEntry, ...]
    backup_event_ids: frozenset[str]
    activations: tuple[MeasurementBackupActivation, ...]
    required_actions: tuple[TrainingRequiredAction, ...]


def _has_valid_attempt(
    attempt_statuses: AttemptStatuses,
    *,
    event_id: str,
    days: Sequence[int],
) -> bool:
    statuses = attempt_statuses.get(event_id, {})
    return any(statuses.get(attempt_day) == "valid" for attempt_day in days)


def resolve_measurement_day(
    *,
    block: V3Block,
    schedule: Sequence[CompiledEntry],
    day: int,
    attempt_statuses: AttemptStatuses,
) -> MeasurementDayResolution:
    """Resolve authored backup substitutions and exhausted-event actions.

    Events are considered in their imported order and running slots in the
    compiled schedule's order. If two events compete for fewer running slots,
    the earlier event wins and the other remains absent; no non-running entry
    is ever displaced. A later read, strictly after that event's final
    authored day, exposes its imported ``on_all_missed`` action when required.
    """
    entries = [entry for entry in schedule if entry.day == day]
    available_running_indexes = [
        index for index, entry in enumerate(entries) if is_running_bundle(entry.bundle_id)
    ]
    activated: list[str] = []
    activations: list[MeasurementBackupActivation] = []

    for event in block.measurement_events:
        if day not in event.backup_days:
            continue
        prior_days = [
            attempt_day
            for attempt_day in (event.scheduled_day, *event.backup_days)
            if attempt_day < day
        ]
        if _has_valid_attempt(
            attempt_statuses,
            event_id=event.id,
            days=prior_days,
        ):
            continue
        original = next(
            (
                entry
                for entry in schedule
                if entry.day == event.scheduled_day
                and entry.card.id == event.card_id
                and is_running_bundle(entry.bundle_id)
            ),
            None,
        )
        if original is None or not available_running_indexes:
            continue

        target_index = available_running_indexes.pop(0)
        target = entries[target_index]
        assignment = original.assignment.model_copy(
            update={
                "day": day,
                "slot": target.slot,
                "card_id": original.card.id,
            }
        )
        entries[target_index] = replace(
            original,
            day=day,
            slot=target.slot,
            assignment=assignment,
        )
        activated.append(event.id)
        activations.append(
            MeasurementBackupActivation(event_id=event.id, entry_index=target_index)
        )

    required_actions = tuple(
        TrainingRequiredAction(event_id=event.id, action=event.on_all_missed)
        for event in block.measurement_events
        if event.required
        and day > max(event.scheduled_day, *event.backup_days)
        and not _has_valid_attempt(
            attempt_statuses,
            event_id=event.id,
            days=(event.scheduled_day, *event.backup_days),
        )
    )
    return MeasurementDayResolution(
        entries=tuple(entries),
        backup_event_ids=frozenset(activated),
        activations=tuple(activations),
        required_actions=required_actions,
    )


__all__ = [
    "MeasurementBackupActivation",
    "MeasurementDayResolution",
    "resolve_measurement_day",
]
