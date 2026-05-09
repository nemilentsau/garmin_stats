"""Artifact bundle preview and import use cases."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from pydantic import ValidationError

from app.domains.artifacts.contracts import (
    ArtifactBundleDelta,
    ArtifactBundleDeltaAction,
    ArtifactBundleImportResponse,
    ArtifactBundleIssue,
    ArtifactBundleItemKind,
    ArtifactBundlePreviewResponse,
    ArtifactBundleSpec,
    AssistantArtifact,
    RoutineSpec,
)
from app.domains.artifacts.dependencies import ArtifactRepository
from app.domains.routines.dependencies import RoutineRepository
from app.utils.timeutil import now_iso

from .bundle_ids import bundle_artifact_id, next_bundle_artifact_revision
from .validation import validate_card_template_payload, validate_routine_spec_payload


@dataclass(frozen=True)
class _PreparedBundleArtifact:
    artifact_id: str
    kind: ArtifactBundleItemKind
    target_id: str
    payload_json: dict[str, object]
    action: ArtifactBundleDeltaAction
    summary: str


_RESERVED_PLACEHOLDER_BUNDLE_IDS = frozenset({"proper-routine-bundle"})
_RESERVED_PLACEHOLDER_BUNDLE_NAMES = frozenset({"Proper Routine Bundle"})
_RESERVED_PLACEHOLDER_ID_PREFIXES = ("starter-",)
_RESERVED_PLACEHOLDER_TAGS = frozenset({"starter"})
_RESERVED_PLACEHOLDER_PHRASES = (
    "replace with llm-authored json",
    "starter proper-spec bundle",
)


def _artifact_target_exists(
    routines_repo: RoutineRepository,
    kind: ArtifactBundleItemKind,
    target_id: str,
) -> bool:
    if kind == "card_template":
        return routines_repo.get_card_template(target_id) is not None
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
            _artifact_target_exists(routines_repo, kind, target_id)
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
    revision = next_bundle_artifact_revision(artifact_repo, bundle_id, kind, target_id)
    return ArtifactBundleDelta(
        artifact_id=bundle_artifact_id(bundle_id, kind, target_id, revision),
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

        card_errors, _requested_renderer = validate_card_template_payload(payload)
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

        routine_errors = validate_routine_spec_payload(
            artifact_repo,
            routines_repo,
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
