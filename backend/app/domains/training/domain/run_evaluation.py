"""Pure effective-execution policy for scheduled training cards."""

from app.domains.training.contracts import (
    TrainingCardStatus,
    TrainingExecutionEvaluation,
)


def effective_execution(
    *, log_status: TrainingCardStatus, run_id: str | None
) -> TrainingExecutionEvaluation:
    """Resolve completion without changing the persisted card log."""
    if log_status != "pending":
        return TrainingExecutionEvaluation(
            status=log_status, source="manual_log", run_id=run_id
        )
    if run_id is not None:
        return TrainingExecutionEvaluation(
            status="completed", source="tracked_run", run_id=run_id
        )
    return TrainingExecutionEvaluation(status="pending", source="none")
