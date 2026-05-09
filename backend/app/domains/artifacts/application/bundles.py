"""Artifact bundle preview and import use cases.

Bundle planning validates card and routine payloads together, reports whether
each target creates or updates live runtime data, and persists versioned drafts
without directly compiling them.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
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

from .activation import activate_assistant_artifact
from .bundle_ids import bundle_artifact_id, next_bundle_artifact_revision
from .validation import validate_card_template_payload, validate_routine_spec_payload


@dataclass(frozen=True)
class _PreparedBundleArtifact:
    """Planned bundle artifact: the public delta plus the payload to persist."""

    delta: ArtifactBundleDelta
    payload_json: dict[str, object]


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


def _reserved_value_issue(
    *, path: str, descriptor: str, value: str
) -> ArtifactBundleIssue:
    return ArtifactBundleIssue(
        path=path,
        message=(
            f"{descriptor} '{value}' is reserved for placeholder/demo content "
            "and cannot be imported"
        ),
    )


def _reserved_text_issue(
    *, path: str, descriptor: str, follow_up: str
) -> ArtifactBundleIssue:
    return ArtifactBundleIssue(
        path=path,
        message=(
            f"{descriptor} still contains placeholder authoring instructions; "
            f"{follow_up}"
        ),
    )


def _reserved_tags_issue(
    *, path: str, reserved_tags: list[str]
) -> ArtifactBundleIssue:
    return ArtifactBundleIssue(
        path=path,
        message=(
            f"Reserved placeholder/demo tag(s) {', '.join(reserved_tags)} found; "
            "remove them before import"
        ),
    )


def _placeholder_item_issues(
    *,
    path_prefix: str,
    kind_label: str,
    item_id: str,
    text_field_name: str,
    text_field_value: str | None,
    tags: Iterable[str],
) -> list[ArtifactBundleIssue]:
    """Issues for one card_template or routine_spec entry in a bundle."""
    issues: list[ArtifactBundleIssue] = []
    if _starts_with_reserved_placeholder_prefix(item_id):
        issues.append(
            _reserved_value_issue(
                path=f"{path_prefix}.id",
                descriptor=f"{kind_label} id",
                value=item_id,
            )
        )
    if _contains_reserved_placeholder_phrase(text_field_value):
        issues.append(
            _reserved_text_issue(
                path=f"{path_prefix}.{text_field_name}",
                descriptor=f"{kind_label} {text_field_name}",
                follow_up="replace it with real bundle metadata",
            )
        )
    reserved_tags = sorted(set(tags) & _RESERVED_PLACEHOLDER_TAGS)
    if reserved_tags:
        issues.append(
            _reserved_tags_issue(
                path=f"{path_prefix}.tags",
                reserved_tags=reserved_tags,
            )
        )
    return issues


def _validate_placeholder_bundle_content(bundle: ArtifactBundleSpec) -> list[ArtifactBundleIssue]:
    issues: list[ArtifactBundleIssue] = []

    if bundle.id in _RESERVED_PLACEHOLDER_BUNDLE_IDS:
        issues.append(
            _reserved_value_issue(
                path="bundle.id", descriptor="Bundle id", value=bundle.id,
            )
        )
    if bundle.name in _RESERVED_PLACEHOLDER_BUNDLE_NAMES:
        issues.append(
            _reserved_value_issue(
                path="bundle.name", descriptor="Bundle name", value=bundle.name,
            )
        )
    if _contains_reserved_placeholder_phrase(bundle.description):
        issues.append(
            _reserved_text_issue(
                path="bundle.description",
                descriptor="Bundle description",
                follow_up="paste a real bundle before preview/import",
            )
        )

    for index, card in enumerate(bundle.card_templates):
        issues.extend(
            _placeholder_item_issues(
                path_prefix=f"card_templates.{index}",
                kind_label="card_template",
                item_id=card.id,
                text_field_name="summary",
                text_field_value=card.summary,
                tags=card.tags,
            )
        )

    for index, routine in enumerate(bundle.routine_specs):
        issues.extend(
            _placeholder_item_issues(
                path_prefix=f"routine_specs.{index}",
                kind_label="routine_spec",
                item_id=routine.id,
                text_field_name="notes",
                text_field_value=routine.notes,
                tags=routine.tags,
            )
        )
        for assignment_index, assignment in enumerate(routine.assignments):
            if _starts_with_reserved_placeholder_prefix(assignment.id):
                issues.append(
                    _reserved_value_issue(
                        path=f"routine_specs.{index}.assignments.{assignment_index}.id",
                        descriptor="Assignment id",
                        value=assignment.id,
                    )
                )

    return issues


def _record_duplicate_id_issue(
    *,
    ids_seen: set[str],
    kind: ArtifactBundleItemKind,
    item_id: str,
    path_prefix: str,
    issues: list[ArtifactBundleIssue],
) -> bool:
    """Record a duplicate-id issue and return True; otherwise mark id seen."""
    if item_id in ids_seen:
        issues.append(
            ArtifactBundleIssue(
                path=f"{path_prefix}.id",
                message=f"Duplicate {kind} id '{item_id}' in bundle",
            )
        )
        return True
    ids_seen.add(item_id)
    return False


def _record_payload_issues(
    errors: list[str],
    *,
    path_prefix: str,
    issues: list[ArtifactBundleIssue],
) -> None:
    for error in errors:
        issues.append(ArtifactBundleIssue(path=path_prefix, message=error))


def _record_prepared_artifact(
    *,
    artifact_repo: ArtifactRepository,
    routines_repo: RoutineRepository,
    bundle_id: str,
    kind: ArtifactBundleItemKind,
    target_id: str,
    payload: dict[str, object],
    existing_draft_ids: set[str],
    prepared: list[_PreparedBundleArtifact],
) -> None:
    delta = _bundle_delta_for_artifact(
        artifact_repo=artifact_repo,
        routines_repo=routines_repo,
        bundle_id=bundle_id,
        kind=kind,
        target_id=target_id,
        payload_json=payload,
        existing_draft_ids=existing_draft_ids,
    )
    prepared.append(_PreparedBundleArtifact(delta=delta, payload_json=payload))


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
        path_prefix = f"card_templates.{index}"
        if _record_duplicate_id_issue(
            ids_seen=card_ids_seen,
            kind="card_template",
            item_id=card.id,
            path_prefix=path_prefix,
            issues=issues,
        ):
            continue

        payload = card.model_dump()
        card_errors, _requested_renderer = validate_card_template_payload(payload)
        _record_payload_issues(card_errors, path_prefix=path_prefix, issues=issues)

        _record_prepared_artifact(
            artifact_repo=artifact_repo,
            routines_repo=routines_repo,
            bundle_id=bundle.id,
            kind="card_template",
            target_id=card.id,
            payload=payload,
            existing_draft_ids=existing_draft_ids,
            prepared=prepared,
        )

    for index, routine in enumerate(bundle.routine_specs):
        path_prefix = f"routine_specs.{index}"
        if _record_duplicate_id_issue(
            ids_seen=routine_ids_seen,
            kind="routine_spec",
            item_id=routine.id,
            path_prefix=path_prefix,
            issues=issues,
        ):
            continue

        payload = routine.model_dump()
        routine_errors = validate_routine_spec_payload(
            artifact_repo,
            routines_repo,
            payload,
            additional_card_ids=bundled_card_ids,
        )
        _record_payload_issues(routine_errors, path_prefix=path_prefix, issues=issues)

        for assignment_index, assignment in enumerate(routine.assignments):
            assignment_path = f"{path_prefix}.assignments.{assignment_index}.id"
            if assignment.id in assignment_ids_seen:
                issues.append(
                    ArtifactBundleIssue(
                        path=assignment_path,
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
                        path=assignment_path,
                        message=(
                            f"Assignment id '{assignment.id}' already belongs to routine "
                            f"{routine_names}"
                        ),
                    )
                )

        _record_prepared_artifact(
            artifact_repo=artifact_repo,
            routines_repo=routines_repo,
            bundle_id=bundle.id,
            kind="routine_spec",
            target_id=routine.id,
            payload=payload,
            existing_draft_ids=existing_draft_ids,
            prepared=prepared,
        )

    return issues, prepared


def preview_artifact_bundle(
    artifact_repo: ArtifactRepository,
    routines_repo: RoutineRepository,
    bundle: ArtifactBundleSpec,
) -> ArtifactBundlePreviewResponse:
    """Return validation issues and planned bundle deltas without writing."""
    issues, prepared = _build_bundle_plan(artifact_repo, routines_repo, bundle)
    return ArtifactBundlePreviewResponse(
        bundle_id=bundle.id,
        bundle_name=bundle.name,
        valid=not issues,
        issues=issues,
        deltas=[item.delta for item in prepared],
    )


def import_artifact_bundle(
    artifact_repo: ArtifactRepository,
    routines_repo: RoutineRepository,
    bundle: ArtifactBundleSpec,
) -> ArtifactBundleImportResponse:
    """Persist all artifacts from a valid bundle as validated drafts."""
    issues, prepared = _build_bundle_plan(artifact_repo, routines_repo, bundle)
    if issues:
        raise ValueError("Bundle has blocking issues; preview and resolve them before import")

    now = now_iso()
    artifacts = [
        AssistantArtifact(
            id=item.delta.artifact_id,
            kind=item.delta.kind,
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
        deltas=[item.delta for item in prepared],
    )


def import_and_activate_artifact_bundle(
    artifact_repo: ArtifactRepository,
    routines_repo: RoutineRepository,
    bundle: ArtifactBundleSpec,
) -> ArtifactBundleImportResponse:
    """Persist a valid bundle and activate the imported artifacts."""
    result = import_artifact_bundle(artifact_repo, routines_repo, bundle)
    for delta in result.deltas:
        activate_assistant_artifact(
            artifact_repo,
            routines_repo,
            delta.artifact_id,
        )
    return result
