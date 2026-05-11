"""Placeholder-content validation for artifact bundle imports.

This module owns guard rails that reject demo or scaffolded bundle content
before preview/import proceeds. Bundle planning passes a fully parsed bundle
spec here and keeps persistence, delta planning, and activation concerns in the
bundle orchestration module.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.domains.artifacts.contracts import (
    ArtifactBundleIssue,
    ArtifactBundleSpec,
)

_RESERVED_PLACEHOLDER_BUNDLE_IDS = frozenset({"proper-routine-bundle"})
_RESERVED_PLACEHOLDER_BUNDLE_NAMES = frozenset({"Proper Routine Bundle"})
_RESERVED_PLACEHOLDER_ID_PREFIXES = ("starter-",)
_RESERVED_PLACEHOLDER_TAGS = frozenset({"starter"})
_RESERVED_PLACEHOLDER_PHRASES = (
    "replace with llm-authored json",
    "starter proper-spec bundle",
)


def validate_placeholder_bundle_content(
    bundle: ArtifactBundleSpec,
) -> list[ArtifactBundleIssue]:
    """Return issues for reserved demo/scaffold content in a bundle."""
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
    """Return reserved-content issues for one card or routine bundle item."""
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
