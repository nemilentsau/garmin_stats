"""Routine activation use case."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

from app.domains.routines.contracts import RoutineAssignment, RoutineSchedule
from app.models import AssistantArtifact, RoutineSpec

from .ports import RoutineRepository


def compile_routine_artifact(
    repo: RoutineRepository,
    artifact: AssistantArtifact,
    *,
    activate_card_template_dependency: Callable[[str, AssistantArtifact | None], None],
) -> RoutineSchedule:
    spec = RoutineSpec.model_validate(artifact.payload_json)
    for assignment in spec.assignments:
        activate_card_template_dependency(assignment.card_template_id, artifact)

    routine = RoutineSchedule(
        id=spec.id,
        name=spec.name,
        status=spec.status,
        start_date=spec.start_date,
        end_date=spec.end_date,
        tags=spec.tags,
        notes=spec.notes,
        source_artifact_id=artifact.id,
    )
    start = date.fromisoformat(spec.start_date)
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
        for assignment in spec.assignments
    ]
    repo.save_routine_with_assignments(
        routine=routine,
        assignments=compiled_assignments,
    )
    return routine
