"""Map coach-owned assessment persistence into training-local contracts.

This adapter lives in bootstrap so coach owns the durable review/message
records while training depends only on its read-only projection and protocol.
"""

from __future__ import annotations

from app.domains.coach.adapters import SqliteCoachRepository
from app.domains.training.contracts import TrainingMeasurementAssessment


class CoachMeasurementAssessmentPort:
    """Training assessment port backed by the public coach repository read."""

    def __init__(self, coach_repo: SqliteCoachRepository) -> None:
        self._coach_repo = coach_repo

    def latest_for(
        self, run_id: str, occurrence_key: str
    ) -> TrainingMeasurementAssessment | None:
        record = self._coach_repo.latest_measurement_assessment(run_id, occurrence_key)
        if record is None:
            return None
        return TrainingMeasurementAssessment(
            status=record.assessment.status,
            rationale=record.assessment.rationale,
            source_id=record.source_id,
        )
