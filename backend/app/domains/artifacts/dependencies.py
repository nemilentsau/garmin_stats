"""Ports consumed by assistant artifact use cases.

Application modules depend on these protocols instead of concrete SQLite
persistence. Bootstrap wires the production adapter into routes.
"""

from __future__ import annotations

from typing import Protocol

from app.domains.artifacts.contracts import AssistantArtifact


class ArtifactRepository(Protocol):
    """Persistence port for staged assistant artifacts and bundle revisions."""

    def save_assistant_artifact(self, artifact: AssistantArtifact) -> None: ...

    def save_assistant_artifacts_batch(self, artifacts: list[AssistantArtifact]) -> None: ...

    def get_assistant_artifact(self, artifact_id: str) -> AssistantArtifact | None: ...

    def list_assistant_artifacts(
        self,
        *,
        kind: str | None = None,
        status: str | None = None,
    ) -> list[AssistantArtifact]: ...

    def get_assistant_artifact_by_payload_id(
        self,
        kind: str,
        payload_id: str,
        statuses: tuple[str, ...],
    ) -> AssistantArtifact | None: ...

    def get_max_artifact_revision(self, *, kind: str, id_prefix: str) -> int: ...
