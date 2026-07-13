"""Effective execution evaluation for scheduled training cards."""

import pytest

from app.domains.training.contracts import TrainingCardStatus
from app.domains.training.domain.run_evaluation import effective_execution


@pytest.mark.parametrize("status", ["completed", "partial", "skipped"])
def test_manual_status_remains_authoritative_when_run_is_associated(
    status: TrainingCardStatus,
):
    execution = effective_execution(log_status=status, run_id="r1")

    assert execution.status == status
    assert execution.source == "manual_log"
    assert execution.run_id == "r1"


def test_pending_status_becomes_completed_when_run_is_associated():
    execution = effective_execution(log_status="pending", run_id="r1")

    assert execution.status == "completed"
    assert execution.source == "tracked_run"
    assert execution.run_id == "r1"


def test_pending_status_remains_pending_without_associated_run():
    execution = effective_execution(log_status="pending", run_id=None)

    assert execution.status == "pending"
    assert execution.source == "none"
    assert execution.run_id is None
