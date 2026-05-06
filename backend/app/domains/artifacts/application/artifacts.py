"""Validation and compilation for assistant-authored routine and card specs."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from uuid import uuid4

from pydantic import ValidationError

from app.domains.routines.application.activation import compile_routine_artifact
from app.domains.routines.application.ports import RoutineRepository
from app.models import (
    ArtifactBundleDelta,
    ArtifactBundleDeltaAction,
    ArtifactBundleImportResponse,
    ArtifactBundleIssue,
    ArtifactBundleItemKind,
    ArtifactBundlePreviewResponse,
    ArtifactBundleSpec,
    AssistantArtifact,
    AssistantArtifactCreateRequest,
    AssistantArtifactsResponse,
    CapabilityRequestSpec,
    CardTemplate,
    CardTemplateSpec,
    CardTemplatesResponse,
    ChecklistBlockPayloadSpec,
    ExerciseBlockPayloadSpec,
    RoutineSchedule,
    RoutineSpec,
    TimerSessionPayloadSpec,
)
from app.utils.timeutil import now_iso

from .ports import ArtifactRepository

_PAYLOAD_MODELS = {
    "timer_session": TimerSessionPayloadSpec,
    "checklist_block": ChecklistBlockPayloadSpec,
    "exercise_block": ExerciseBlockPayloadSpec,
}


@dataclass(frozen=True)
class _PreparedBundleArtifact:
    artifact_id: str
    kind: ArtifactBundleItemKind
    target_id: str
    payload_json: dict[str, object]
    action: ArtifactBundleDeltaAction
    summary: str


@dataclass(frozen=True)
class _BundleArtifactRef:
    bundle_id: str
    kind: ArtifactBundleItemKind
    target_id: str
    revision: int


_BUNDLE_ARTIFACT_ID_RE = re.compile(
    r"^bundle:(?P<bundle_id>.+?):"
    r"(?P<kind>card_template|routine_spec):"
    r"(?P<target_id>.+):r(?P<revision>\d+)$"
)
_RESERVED_PLACEHOLDER_BUNDLE_IDS = frozenset({"proper-routine-bundle"})
_RESERVED_PLACEHOLDER_BUNDLE_NAMES = frozenset({"Proper Routine Bundle"})
_RESERVED_PLACEHOLDER_ID_PREFIXES = ("starter-",)
_RESERVED_PLACEHOLDER_TAGS = frozenset({"starter"})
_RESERVED_PLACEHOLDER_PHRASES = (
    "replace with llm-authored json",
    "starter proper-spec bundle",
)


def _format_validation_errors(exc: ValidationError) -> list[str]:
    errors: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"])
        msg = err["msg"]
        errors.append(f"{loc}: {msg}" if loc else msg)
    return errors


def _card_spec_artifact_by_card_id(
    repo: ArtifactRepository,
    card_id: str,
) -> AssistantArtifact | None:
    return repo.get_assistant_artifact_by_payload_id(
        "card_template", card_id, ("validated", "activated"),
    )


def _validate_card_template_payload(
    payload_json: dict[str, object],
) -> tuple[list[str], str | None]:
    requested_renderer = payload_json.get("renderer")
    if not isinstance(requested_renderer, str):
        return ["renderer: Field required"], None

    if requested_renderer not in _PAYLOAD_MODELS:
        return [f"renderer: Unsupported renderer family '{requested_renderer}'"], requested_renderer

    try:
        spec = CardTemplateSpec.model_validate(payload_json)
    except ValidationError as exc:
        return _format_validation_errors(exc), requested_renderer

    payload_model = _PAYLOAD_MODELS[spec.renderer]
    try:
        payload_model.model_validate(spec.payload)
    except ValidationError as exc:
        return _format_validation_errors(exc), requested_renderer

    return [], requested_renderer


def _validate_routine_spec_payload(
    repo: ArtifactRepository,
    payload_json: dict[str, object],
    *,
    additional_card_ids: set[str] | None = None,
) -> list[str]:
    try:
        spec = RoutineSpec.model_validate(payload_json)
    except ValidationError as exc:
        return _format_validation_errors(exc)

    errors: list[str] = []
    additional_card_ids = additional_card_ids or set()
    for assignment in spec.assignments:
        if assignment.day < 1:
            errors.append(
                f"assignments.{assignment.id}.day: must be >= 1"
            )
        if (
            assignment.card_template_id not in additional_card_ids
            and (
            repo.get_card_template(assignment.card_template_id) is None
            and _card_spec_artifact_by_card_id(repo, assignment.card_template_id) is None
            )
        ):
            errors.append(
                "assignments."
                f"{assignment.id}.card_template_id: unknown card template "
                f"'{assignment.card_template_id}'"
            )
    return errors


def _validate_capability_request_payload(payload_json: dict[str, object]) -> list[str]:
    try:
        CapabilityRequestSpec.model_validate(payload_json)
    except ValidationError as exc:
        return _format_validation_errors(exc)
    return []


def _system_capability_request(
    repo: ArtifactRepository,
    *,
    requested_renderer: str,
    source_artifact: AssistantArtifactCreateRequest,
) -> AssistantArtifact:
    now = now_iso()
    artifact = AssistantArtifact(
        id=f"capreq-{uuid4().hex}",
        kind="capability_request",
        schema_version=1,
        status="draft",
        source_thread_id=source_artifact.source_thread_id,
        source_snapshot_id=source_artifact.source_snapshot_id,
        payload_json=CapabilityRequestSpec(
            requested_renderer=requested_renderer,
            reason=(
                f"Assistant draft '{source_artifact.id}' requested unsupported renderer "
                f"'{requested_renderer}'"
            ),
            source_artifact_id=source_artifact.id,
            payload_example_json=source_artifact.payload_json,
        ).model_dump(),
        created_at=now,
        updated_at=now,
    )
    repo.save_assistant_artifact(artifact)
    return artifact


def create_assistant_artifact(
    repo: ArtifactRepository,
    request: AssistantArtifactCreateRequest,
) -> AssistantArtifact:
    now = now_iso()
    errors: list[str] = []
    requested_renderer: str | None = None

    if request.kind == "card_template":
        errors, requested_renderer = _validate_card_template_payload(request.payload_json)
    elif request.kind == "routine_spec":
        errors = _validate_routine_spec_payload(repo, request.payload_json)
    else:
        errors = _validate_capability_request_payload(request.payload_json)

    status = "validated" if not errors else "invalid"
    artifact = AssistantArtifact(
        id=request.id,
        kind=request.kind,
        schema_version=request.schema_version,
        status=status,
        source_thread_id=request.source_thread_id,
        source_snapshot_id=request.source_snapshot_id,
        payload_json=request.payload_json,
        validation_errors=errors,
        created_at=now,
        updated_at=now,
    )
    repo.save_assistant_artifact(artifact)

    if (
        request.kind == "card_template"
        and requested_renderer
        and requested_renderer not in _PAYLOAD_MODELS
    ):
        _system_capability_request(
            repo,
            requested_renderer=requested_renderer,
            source_artifact=request,
        )

    return artifact


def _bundle_artifact_prefix(bundle_id: str, kind: ArtifactBundleItemKind, target_id: str) -> str:
    return f"bundle:{bundle_id}:{kind}:{target_id}:r"


def _next_bundle_artifact_revision(
    repo: ArtifactRepository,
    bundle_id: str,
    kind: ArtifactBundleItemKind,
    target_id: str,
) -> int:
    prefix = _bundle_artifact_prefix(bundle_id, kind, target_id)
    return repo.get_max_artifact_revision(kind=kind, id_prefix=prefix) + 1


def _bundle_artifact_id(
    bundle_id: str,
    kind: ArtifactBundleItemKind,
    target_id: str,
    revision: int,
) -> str:
    return f"{_bundle_artifact_prefix(bundle_id, kind, target_id)}{revision}"


def _parse_bundle_artifact_id(artifact_id: str) -> _BundleArtifactRef | None:
    match = _BUNDLE_ARTIFACT_ID_RE.match(artifact_id)
    if match is None:
        return None
    groups = match.groupdict()
    return _BundleArtifactRef(
        bundle_id=groups["bundle_id"],
        kind=groups["kind"],  # type: ignore[arg-type]
        target_id=groups["target_id"],
        revision=int(groups["revision"]),
    )


def _artifact_target_exists(
    artifact_repo: ArtifactRepository,
    routines_repo: RoutineRepository,
    kind: ArtifactBundleItemKind,
    target_id: str,
) -> bool:
    if kind == "card_template":
        return artifact_repo.get_card_template(target_id) is not None
    return routines_repo.get_routine(target_id) is not None


def _build_existing_draft_ids(
    repo: ArtifactRepository,
    kinds: set[ArtifactBundleItemKind],
) -> set[str]:
    ids: set[str] = set()
    for kind in kinds:
        for artifact in repo.list_assistant_artifacts(kind=kind):
            target_id = artifact.payload_json.get("id")
            if isinstance(target_id, str):
                ids.add(f"{kind}:{target_id}")
    return ids


def _bundle_delta_summary(
    artifact_repo: ArtifactRepository,
    routines_repo: RoutineRepository,
    kind: ArtifactBundleItemKind,
    target_id: str,
    payload_json: dict[str, object],
    *,
    existing_draft_ids: set[str],
) -> tuple[ArtifactBundleDeltaAction, str]:
    action: ArtifactBundleDeltaAction = (
        "update"
        if (
            _artifact_target_exists(artifact_repo, routines_repo, kind, target_id)
            or f"{kind}:{target_id}" in existing_draft_ids
        )
        else "create"
    )
    if kind == "card_template":
        summary = (
            "Updates an active live card" if action == "update" else "Creates a new live card"
        )
    else:
        assignments = payload_json.get("assignments")
        assignment_count = len(assignments) if isinstance(assignments, list) else 0
        verb = "Updates" if action == "update" else "Creates"
        summary = f"{verb} a live routine · {assignment_count} assignments"
    return action, summary


def _bundle_delta_for_artifact(
    *,
    artifact_repo: ArtifactRepository,
    routines_repo: RoutineRepository,
    bundle_id: str,
    kind: ArtifactBundleItemKind,
    target_id: str,
    payload_json: dict[str, object],
    existing_draft_ids: set[str],
) -> ArtifactBundleDelta:
    action, summary = _bundle_delta_summary(
        artifact_repo,
        routines_repo,
        kind,
        target_id,
        payload_json,
        existing_draft_ids=existing_draft_ids,
    )
    revision = _next_bundle_artifact_revision(artifact_repo, bundle_id, kind, target_id)
    return ArtifactBundleDelta(
        artifact_id=_bundle_artifact_id(bundle_id, kind, target_id, revision),
        kind=kind,
        target_id=target_id,
        action=action,
        summary=summary,
    )


def _existing_assignment_routine_ids(
    artifact_repo: ArtifactRepository,
    routines_repo: RoutineRepository,
) -> dict[str, set[str]]:
    routine_ids_by_assignment_id: dict[str, set[str]] = defaultdict(set)

    for assignment in routines_repo.list_assignments():
        routine_ids_by_assignment_id[assignment.id].add(assignment.routine_id)

    for artifact in artifact_repo.list_assistant_artifacts(kind="routine_spec"):
        if artifact.status not in {"validated", "activated"}:
            continue
        try:
            spec = RoutineSpec.model_validate(artifact.payload_json)
        except ValidationError:
            continue
        for assignment in spec.assignments:
            routine_ids_by_assignment_id[assignment.id].add(spec.id)

    return routine_ids_by_assignment_id


def _starts_with_reserved_placeholder_prefix(value: str) -> bool:
    return any(value.startswith(prefix) for prefix in _RESERVED_PLACEHOLDER_ID_PREFIXES)


def _contains_reserved_placeholder_phrase(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.casefold()
    return any(phrase in normalized for phrase in _RESERVED_PLACEHOLDER_PHRASES)


def _validate_placeholder_bundle_content(bundle: ArtifactBundleSpec) -> list[ArtifactBundleIssue]:
    issues: list[ArtifactBundleIssue] = []

    if bundle.id in _RESERVED_PLACEHOLDER_BUNDLE_IDS:
        issues.append(
            ArtifactBundleIssue(
                path="bundle.id",
                message=(
                    f"Bundle id '{bundle.id}' is reserved for placeholder/demo content and "
                    "cannot be imported"
                ),
            )
        )
    if bundle.name in _RESERVED_PLACEHOLDER_BUNDLE_NAMES:
        issues.append(
            ArtifactBundleIssue(
                path="bundle.name",
                message=(
                    f"Bundle name '{bundle.name}' is reserved for placeholder/demo content "
                    "and cannot be imported"
                ),
            )
        )
    if _contains_reserved_placeholder_phrase(bundle.description):
        issues.append(
            ArtifactBundleIssue(
                path="bundle.description",
                message=(
                    "Bundle description still contains placeholder authoring instructions; "
                    "paste a real bundle before preview/import"
                ),
            )
        )

    for index, card in enumerate(bundle.card_templates):
        if _starts_with_reserved_placeholder_prefix(card.id):
            issues.append(
                ArtifactBundleIssue(
                    path=f"card_templates.{index}.id",
                    message=(
                        f"card_template id '{card.id}' is reserved for placeholder/demo "
                        "content and cannot be imported"
                    ),
                )
            )
        if _contains_reserved_placeholder_phrase(card.summary):
            issues.append(
                ArtifactBundleIssue(
                    path=f"card_templates.{index}.summary",
                    message=(
                        "card_template summary still contains placeholder authoring "
                        "instructions; replace it with real bundle metadata"
                    ),
                )
            )
        if reserved_tags := sorted(set(card.tags) & _RESERVED_PLACEHOLDER_TAGS):
            issues.append(
                ArtifactBundleIssue(
                    path=f"card_templates.{index}.tags",
                    message=(
                        f"Reserved placeholder/demo tag(s) {', '.join(reserved_tags)} found; "
                        "remove them before import"
                    ),
                )
            )

    for index, routine in enumerate(bundle.routine_specs):
        if _starts_with_reserved_placeholder_prefix(routine.id):
            issues.append(
                ArtifactBundleIssue(
                    path=f"routine_specs.{index}.id",
                    message=(
                        f"routine_spec id '{routine.id}' is reserved for placeholder/demo "
                        "content and cannot be imported"
                    ),
                )
            )
        if _contains_reserved_placeholder_phrase(routine.notes):
            issues.append(
                ArtifactBundleIssue(
                    path=f"routine_specs.{index}.notes",
                    message=(
                        "routine_spec notes still contain placeholder authoring instructions; "
                        "replace them with real bundle metadata"
                    ),
                )
            )
        if reserved_tags := sorted(set(routine.tags) & _RESERVED_PLACEHOLDER_TAGS):
            issues.append(
                ArtifactBundleIssue(
                    path=f"routine_specs.{index}.tags",
                    message=(
                        f"Reserved placeholder/demo tag(s) {', '.join(reserved_tags)} found; "
                        "remove them before import"
                    ),
                )
            )
        for assignment_index, assignment in enumerate(routine.assignments):
            if _starts_with_reserved_placeholder_prefix(assignment.id):
                issues.append(
                    ArtifactBundleIssue(
                        path=f"routine_specs.{index}.assignments.{assignment_index}.id",
                        message=(
                            f"Assignment id '{assignment.id}' is reserved for placeholder/demo "
                            "content and cannot be imported"
                        ),
                    )
                )

    return issues


def _build_bundle_plan(
    artifact_repo: ArtifactRepository,
    routines_repo: RoutineRepository,
    bundle: ArtifactBundleSpec,
) -> tuple[list[ArtifactBundleIssue], list[_PreparedBundleArtifact]]:
    issues: list[ArtifactBundleIssue] = []
    prepared: list[_PreparedBundleArtifact] = []

    if not bundle.card_templates and not bundle.routine_specs:
        issues.append(
            ArtifactBundleIssue(
                path="bundle",
                message="Bundle must include at least one card_template or routine_spec",
            )
        )
        return issues, prepared

    issues.extend(_validate_placeholder_bundle_content(bundle))

    card_ids_seen: set[str] = set()
    routine_ids_seen: set[str] = set()
    assignment_ids_seen: set[str] = set()
    existing_assignment_routine_ids = _existing_assignment_routine_ids(
        artifact_repo,
        routines_repo,
    )
    bundled_card_ids = {card.id for card in bundle.card_templates}
    existing_draft_ids = _build_existing_draft_ids(
        artifact_repo,
        {"card_template", "routine_spec"},
    )

    for index, card in enumerate(bundle.card_templates):
        payload = card.model_dump()
        if card.id in card_ids_seen:
            issues.append(
                ArtifactBundleIssue(
                    path=f"card_templates.{index}.id",
                    message=f"Duplicate card_template id '{card.id}' in bundle",
                )
            )
            continue
        card_ids_seen.add(card.id)

        card_errors, _requested_renderer = _validate_card_template_payload(payload)
        for error in card_errors:
            issues.append(
                ArtifactBundleIssue(
                    path=f"card_templates.{index}",
                    message=error,
                )
            )

        delta = _bundle_delta_for_artifact(
            artifact_repo=artifact_repo,
            routines_repo=routines_repo,
            bundle_id=bundle.id,
            kind="card_template",
            target_id=card.id,
            payload_json=payload,
            existing_draft_ids=existing_draft_ids,
        )
        prepared.append(
            _PreparedBundleArtifact(
                artifact_id=delta.artifact_id,
                kind="card_template",
                target_id=card.id,
                payload_json=payload,
                action=delta.action,
                summary=delta.summary,
            )
        )

    for index, routine in enumerate(bundle.routine_specs):
        payload = routine.model_dump()
        if routine.id in routine_ids_seen:
            issues.append(
                ArtifactBundleIssue(
                    path=f"routine_specs.{index}.id",
                    message=f"Duplicate routine_spec id '{routine.id}' in bundle",
                )
            )
            continue
        routine_ids_seen.add(routine.id)

        routine_errors = _validate_routine_spec_payload(
            artifact_repo,
            payload,
            additional_card_ids=bundled_card_ids,
        )
        for error in routine_errors:
            issues.append(
                ArtifactBundleIssue(
                    path=f"routine_specs.{index}",
                    message=error,
                )
            )

        for assignment_index, assignment in enumerate(routine.assignments):
            if assignment.id in assignment_ids_seen:
                issues.append(
                    ArtifactBundleIssue(
                        path=f"routine_specs.{index}.assignments.{assignment_index}.id",
                        message=f"Duplicate assignment id '{assignment.id}' in bundle",
                    )
                )
                continue
            assignment_ids_seen.add(assignment.id)
            conflicting_routine_ids = sorted(
                existing_assignment_routine_ids.get(assignment.id, set()) - {routine.id}
            )
            if conflicting_routine_ids:
                routine_names = ", ".join(conflicting_routine_ids)
                issues.append(
                    ArtifactBundleIssue(
                        path=f"routine_specs.{index}.assignments.{assignment_index}.id",
                        message=(
                            f"Assignment id '{assignment.id}' already belongs to routine "
                            f"{routine_names}"
                        ),
                    )
                )

        delta = _bundle_delta_for_artifact(
            artifact_repo=artifact_repo,
            routines_repo=routines_repo,
            bundle_id=bundle.id,
            kind="routine_spec",
            target_id=routine.id,
            payload_json=payload,
            existing_draft_ids=existing_draft_ids,
        )
        prepared.append(
            _PreparedBundleArtifact(
                artifact_id=delta.artifact_id,
                kind="routine_spec",
                target_id=routine.id,
                payload_json=payload,
                action=delta.action,
                summary=delta.summary,
            )
        )

    return issues, prepared


def _deltas_from_prepared(prepared: list[_PreparedBundleArtifact]) -> list[ArtifactBundleDelta]:
    return [
        ArtifactBundleDelta(
            artifact_id=item.artifact_id,
            kind=item.kind,
            target_id=item.target_id,
            action=item.action,
            summary=item.summary,
        )
        for item in prepared
    ]


def preview_artifact_bundle(
    artifact_repo: ArtifactRepository,
    routines_repo: RoutineRepository,
    bundle: ArtifactBundleSpec,
) -> ArtifactBundlePreviewResponse:
    issues, prepared = _build_bundle_plan(artifact_repo, routines_repo, bundle)
    return ArtifactBundlePreviewResponse(
        bundle_id=bundle.id,
        bundle_name=bundle.name,
        valid=not issues,
        issues=issues,
        deltas=_deltas_from_prepared(prepared),
    )


def import_artifact_bundle(
    artifact_repo: ArtifactRepository,
    routines_repo: RoutineRepository,
    bundle: ArtifactBundleSpec,
) -> ArtifactBundleImportResponse:
    issues, prepared = _build_bundle_plan(artifact_repo, routines_repo, bundle)
    if issues:
        raise ValueError("Bundle has blocking issues; preview and resolve them before import")

    now = now_iso()
    artifacts = [
        AssistantArtifact(
            id=item.artifact_id,
            kind=item.kind,
            schema_version=bundle.schema_version,
            status="validated",
            payload_json=item.payload_json,
            validation_errors=[],
            created_at=now,
            updated_at=now,
        )
        for item in prepared
    ]
    artifact_repo.save_assistant_artifacts_batch(artifacts)
    return ArtifactBundleImportResponse(
        bundle_id=bundle.id,
        bundle_name=bundle.name,
        imported_artifact_ids=[artifact.id for artifact in artifacts],
        total_imported=len(artifacts),
        deltas=_deltas_from_prepared(prepared),
    )


def list_assistant_artifacts(
    repo: ArtifactRepository,
    *,
    kind: str | None = None,
    status: str | None = None,
) -> AssistantArtifactsResponse:
    artifacts = repo.list_assistant_artifacts(kind=kind, status=status)
    return AssistantArtifactsResponse(artifacts=artifacts)


def get_assistant_artifact(repo: ArtifactRepository, artifact_id: str) -> AssistantArtifact:
    artifact = repo.get_assistant_artifact(artifact_id)
    if artifact is None:
        raise LookupError(f"Assistant artifact {artifact_id} not found")
    return artifact


def _compile_card_template_artifact(
    repo: ArtifactRepository,
    artifact: AssistantArtifact,
) -> CardTemplate:
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
    repo.save_card_template(card)
    return card


def _bundle_card_artifact_for_routine_artifact(
    repo: ArtifactRepository,
    routine_artifact: AssistantArtifact,
    card_id: str,
) -> AssistantArtifact | None:
    bundle_ref = _parse_bundle_artifact_id(routine_artifact.id)
    if bundle_ref is None or bundle_ref.kind != "routine_spec":
        return None
    dependency_id = _bundle_artifact_id(
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
    live_card = artifact_repo.get_card_template(card_id)
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
                _compile_card_template_artifact(artifact_repo, bundle_dependency)
                return
            raise ValueError(f"Card template {card_id} is not ready for activation")
        activate_assistant_artifact(artifact_repo, routines_repo, bundle_dependency.id)
        return

    dependency = _card_spec_artifact_by_card_id(artifact_repo, card_id)
    if dependency is not None:
        if dependency.status == "validated":
            activate_assistant_artifact(artifact_repo, routines_repo, dependency.id)
            return
        if live_card is None or live_card.source_artifact_id != dependency.id:
            _compile_card_template_artifact(artifact_repo, dependency)
        return

    if live_card is not None:
        return

    raise LookupError(f"Card template {card_id} is not available for activation")


def _compile_routine_spec_artifact(
    artifact_repo: ArtifactRepository,
    routines_repo: RoutineRepository,
    artifact: AssistantArtifact,
) -> RoutineSchedule:
    return compile_routine_artifact(
        routines_repo,
        artifact,
        activate_card_template_dependency=lambda card_id, source_artifact: (
            _activate_card_template_dependency(
                artifact_repo,
                routines_repo,
                card_id,
                source_artifact=source_artifact,
            )
        ),
    )


def activate_assistant_artifact(
    artifact_repo: ArtifactRepository,
    routines_repo: RoutineRepository,
    artifact_id: str,
) -> AssistantArtifact:
    artifact = get_assistant_artifact(artifact_repo, artifact_id)
    if artifact.status == "activated":
        return artifact
    if artifact.status != "validated":
        raise ValueError(f"Assistant artifact {artifact_id} is not ready for activation")

    if artifact.kind == "card_template":
        _compile_card_template_artifact(artifact_repo, artifact)
    elif artifact.kind == "routine_spec":
        _compile_routine_spec_artifact(artifact_repo, routines_repo, artifact)
    else:
        raise ValueError("Capability requests cannot be activated")

    updated = artifact.model_copy(update={"status": "activated", "updated_at": now_iso()})
    artifact_repo.save_assistant_artifact(updated)
    return updated


def list_cards(repo: ArtifactRepository, status: str | None = None) -> CardTemplatesResponse:
    cards = repo.list_card_templates(status=status)
    return CardTemplatesResponse(cards=cards)
