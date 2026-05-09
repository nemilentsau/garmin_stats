"""Artifact activation use cases.

Activation converts validated assistant artifacts into live routine-domain
records. Card templates are compiled directly; routine specs delegate schedule
and assignment persistence to the routine activation use case.
"""

from __future__ import annotations

from app.domains.artifacts.contracts import (
    AssistantArtifact,
    CardTemplateSpec,
    RoutineSpec,
)
from app.domains.artifacts.dependencies import ArtifactRepository
from app.domains.routines.application.activation import compile_routine_activation
from app.domains.routines.contracts import (
    CardTemplate,
    RoutineActivationCommand,
    RoutineSchedule,
)
from app.domains.routines.dependencies import RoutineRepository
from app.utils.timeutil import now_iso

from .bundle_ids import bundle_artifact_id, parse_bundle_artifact_id
from .staging import get_assistant_artifact
from .validation import card_spec_artifact_by_card_id


def _compile_card_template_artifact(
    routines_repo: RoutineRepository,
    artifact: AssistantArtifact,
) -> CardTemplate:
    """Persist one validated card-template artifact as a live card template."""
    spec = CardTemplateSpec.model_validate(artifact.payload_json)
    card = CardTemplate(
        id=spec.id,
        name=spec.name,
        renderer=spec.renderer,
        slot_default=spec.slot_default,
        summary=spec.summary,
        tags=spec.tags,
        payload_json=spec.payload,
        source_artifact_id=artifact.id,
    )
    routines_repo.save_card_template(card)
    return card


def _bundle_card_artifact_for_routine_artifact(
    repo: ArtifactRepository,
    routine_artifact: AssistantArtifact,
    card_id: str,
) -> AssistantArtifact | None:
    """Find the same-revision card artifact referenced by a bundle routine."""
    bundle_ref = parse_bundle_artifact_id(routine_artifact.id)
    if bundle_ref is None or bundle_ref.kind != "routine_spec":
        return None
    dependency_id = bundle_artifact_id(
        bundle_ref.bundle_id,
        "card_template",
        card_id,
        bundle_ref.revision,
    )
    dependency = repo.get_assistant_artifact(dependency_id)
    if dependency is None or dependency.kind != "card_template":
        return None
    return dependency


def _activate_card_template_dependency(
    artifact_repo: ArtifactRepository,
    routines_repo: RoutineRepository,
    card_id: str,
    *,
    source_artifact: AssistantArtifact | None = None,
) -> None:
    """Ensure a routine's referenced card template exists in live storage."""
    live_card = routines_repo.get_card_template(card_id)
    bundle_dependency = (
        _bundle_card_artifact_for_routine_artifact(artifact_repo, source_artifact, card_id)
        if source_artifact is not None
        else None
    )
    if bundle_dependency is not None:
        if (
            bundle_dependency.status == "activated"
            and live_card is not None
            and live_card.source_artifact_id == bundle_dependency.id
        ):
            return
        if bundle_dependency.status != "validated":
            if bundle_dependency.status == "activated":
                _compile_card_template_artifact(routines_repo, bundle_dependency)
                return
            raise ValueError(f"Card template {card_id} is not ready for activation")
        activate_assistant_artifact(artifact_repo, routines_repo, bundle_dependency.id)
        return

    dependency = card_spec_artifact_by_card_id(artifact_repo, card_id)
    if dependency is not None:
        if dependency.status == "validated":
            activate_assistant_artifact(artifact_repo, routines_repo, dependency.id)
            return
        if live_card is None or live_card.source_artifact_id != dependency.id:
            _compile_card_template_artifact(routines_repo, dependency)
        return

    if live_card is not None:
        return

    raise LookupError(f"Card template {card_id} is not available for activation")


def _compile_routine_spec_artifact(
    artifact_repo: ArtifactRepository,
    routines_repo: RoutineRepository,
    artifact: AssistantArtifact,
) -> RoutineSchedule:
    """Compile one routine-spec artifact through the routines domain."""
    spec = RoutineSpec.model_validate(artifact.payload_json)
    command = RoutineActivationCommand(
        id=spec.id,
        name=spec.name,
        status=spec.status,
        start_date=spec.start_date,
        end_date=spec.end_date,
        tags=spec.tags,
        notes=spec.notes,
        source_artifact_id=artifact.id,
        assignments=spec.assignments,
    )
    return compile_routine_activation(
        routines_repo,
        command,
        activate_card_template_dependency=lambda card_id: (
            _activate_card_template_dependency(
                artifact_repo,
                routines_repo,
                card_id,
                source_artifact=artifact,
            )
        ),
    )


def activate_assistant_artifact(
    artifact_repo: ArtifactRepository,
    routines_repo: RoutineRepository,
    artifact_id: str,
) -> AssistantArtifact:
    """Activate a validated artifact and record its activated status."""
    artifact = get_assistant_artifact(artifact_repo, artifact_id)
    if artifact.status == "activated":
        return artifact
    if artifact.status != "validated":
        raise ValueError(f"Assistant artifact {artifact_id} is not ready for activation")

    if artifact.kind == "card_template":
        _compile_card_template_artifact(routines_repo, artifact)
    elif artifact.kind == "routine_spec":
        _compile_routine_spec_artifact(artifact_repo, routines_repo, artifact)
    else:
        raise ValueError("Capability requests cannot be activated")

    updated = artifact.model_copy(update={"status": "activated", "updated_at": now_iso()})
    artifact_repo.save_assistant_artifact(updated)
    return updated
