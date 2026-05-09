"""Artifact bundle identifier helpers.

Bundle imports create revisioned artifact ids so a routine artifact can later
activate the matching card-template revision instead of whatever draft is
newest for the same card id.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domains.artifacts.contracts import ArtifactBundleItemKind
from app.domains.artifacts.dependencies import ArtifactRepository


@dataclass(frozen=True)
class BundleArtifactRef:
    """Parsed components of a revisioned bundle artifact id."""

    bundle_id: str
    kind: ArtifactBundleItemKind
    target_id: str
    revision: int


_BUNDLE_ARTIFACT_ID_RE = re.compile(
    r"^bundle:(?P<bundle_id>.+?):"
    r"(?P<kind>card_template|routine_spec):"
    r"(?P<target_id>.+):r(?P<revision>\d+)$"
)


def _bundle_artifact_prefix(bundle_id: str, kind: ArtifactBundleItemKind, target_id: str) -> str:
    return f"bundle:{bundle_id}:{kind}:{target_id}:r"


def next_bundle_artifact_revision(
    repo: ArtifactRepository,
    bundle_id: str,
    kind: ArtifactBundleItemKind,
    target_id: str,
) -> int:
    """Return the next revision number for a bundle item target."""
    prefix = _bundle_artifact_prefix(bundle_id, kind, target_id)
    return repo.get_max_artifact_revision(kind=kind, id_prefix=prefix) + 1


def bundle_artifact_id(
    bundle_id: str,
    kind: ArtifactBundleItemKind,
    target_id: str,
    revision: int,
) -> str:
    """Build the stable artifact id for one imported bundle item revision."""
    return f"{_bundle_artifact_prefix(bundle_id, kind, target_id)}{revision}"


def parse_bundle_artifact_id(artifact_id: str) -> BundleArtifactRef | None:
    """Parse a revisioned bundle artifact id, or return None for normal drafts."""
    match = _BUNDLE_ARTIFACT_ID_RE.match(artifact_id)
    if match is None:
        return None
    groups = match.groupdict()
    return BundleArtifactRef(
        bundle_id=groups["bundle_id"],
        kind=groups["kind"],  # type: ignore[arg-type]
        target_id=groups["target_id"],
        revision=int(groups["revision"]),
    )
