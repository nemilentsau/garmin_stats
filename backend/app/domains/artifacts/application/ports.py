"""Repository contracts for assistant artifact use cases."""

from __future__ import annotations

from typing import Protocol

from app.models import AssistantArtifact, CardTemplate


class ArtifactRepository(Protocol):
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

    def save_card_template(self, card: CardTemplate) -> None: ...

    def get_card_template(self, card_id: str) -> CardTemplate | None: ...

    def list_card_templates(self, *, status: str | None = None) -> list[CardTemplate]: ...
