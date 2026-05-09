"""SQLite repository adapter for assistant artifact use cases."""

from __future__ import annotations

from app.domains.artifacts.contracts import AssistantArtifact
from app.domains.routines.adapters import (
    load_card_template,
    load_card_templates,
    save_card_template,
)
from app.domains.routines.contracts import CardTemplate
from app.infra.database import (
    load_assistant_artifact,
    load_assistant_artifact_by_payload_id,
    load_assistant_artifacts,
    load_max_artifact_revision,
    save_assistant_artifact,
    save_assistant_artifacts_batch,
)


class SqliteArtifactRepository:
    def save_assistant_artifact(self, artifact: AssistantArtifact) -> None:
        save_assistant_artifact(artifact)

    def save_assistant_artifacts_batch(self, artifacts: list[AssistantArtifact]) -> None:
        save_assistant_artifacts_batch(artifacts)

    def get_assistant_artifact(self, artifact_id: str) -> AssistantArtifact | None:
        return load_assistant_artifact(artifact_id)

    def list_assistant_artifacts(
        self,
        *,
        kind: str | None = None,
        status: str | None = None,
    ) -> list[AssistantArtifact]:
        return load_assistant_artifacts(kind=kind, status=status)

    def get_assistant_artifact_by_payload_id(
        self,
        kind: str,
        payload_id: str,
        statuses: tuple[str, ...],
    ) -> AssistantArtifact | None:
        return load_assistant_artifact_by_payload_id(kind, payload_id, statuses)

    def get_max_artifact_revision(self, *, kind: str, id_prefix: str) -> int:
        return load_max_artifact_revision(kind, id_prefix)

    def save_card_template(self, card: CardTemplate) -> None:
        save_card_template(card)

    def get_card_template(self, card_id: str) -> CardTemplate | None:
        return load_card_template(card_id)

    def list_card_templates(self, *, status: str | None = None) -> list[CardTemplate]:
        return load_card_templates(status=status)
