"""Routine activation use case."""

from __future__ import annotations

from datetime import date, timedelta

from app.domains.routines.contracts import (
    RoutineActivationCommand,
    RoutineAssignment,
    RoutineSchedule,
)
from app.domains.routines.dependencies import (
    CardTemplateDependencyActivator,
    RoutineRepository,
)


def compile_routine_activation(
    repo: RoutineRepository,
    command: RoutineActivationCommand,
    *,
    activate_card_template_dependency: CardTemplateDependencyActivator,
) -> RoutineSchedule:
    for assignment in command.assignments:
        activate_card_template_dependency(assignment.card_template_id)

    routine = RoutineSchedule(
        id=command.id,
        name=command.name,
        status=command.status,
        start_date=command.start_date,
        end_date=command.end_date,
        tags=command.tags,
        notes=command.notes,
        source_artifact_id=command.source_artifact_id,
    )
    start = date.fromisoformat(command.start_date)
    compiled_assignments = [
        RoutineAssignment(
            id=assignment.id,
            routine_id=routine.id,
            card_template_id=assignment.card_template_id,
            date=(start + timedelta(days=assignment.day - 1)).isoformat(),
            slot=assignment.slot,
            position=assignment.position,
            prescription_override_json=assignment.prescription_override_json,
        )
        for assignment in command.assignments
    ]
    repo.save_routine_with_assignments(
        routine=routine,
        assignments=compiled_assignments,
    )
    return routine
