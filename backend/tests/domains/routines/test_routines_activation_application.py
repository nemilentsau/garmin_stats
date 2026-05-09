"""Routine activation command tests for the routines domain."""

import pytest

import app.domains.routines.adapters as routine_db
from app.domains.routines.adapters import (
    SqliteRoutineRepository,
    load_routine_assignments,
    load_routine_schedule,
)
from app.domains.routines.application.activation import compile_routine_activation
from app.domains.routines.contracts import (
    RoutineActivationAssignment,
    RoutineActivationCommand,
)


def test_compile_routine_activation_persists_schedule_and_assignments():
    repo = SqliteRoutineRepository()
    command = RoutineActivationCommand(
        id="routine-activation",
        name="Routine Activation",
        start_date="2026-03-02",
        status="active",
        tags=["training"],
        notes="Activation fixture",
        source_artifact_id="artifact-routine-activation",
        assignments=[
            RoutineActivationAssignment(
                id="assignment-activation",
                card_template_id="card-activation",
                day=1,
                slot="morning",
                position=10,
                prescription_override_json={},
            )
        ],
    )

    compile_routine_activation(
        repo,
        command,
        activate_card_template_dependency=lambda *_args: None,
    )

    assert load_routine_schedule("routine-activation") is not None
    assert (
        load_routine_assignments(routine_id="routine-activation")[0].id
        == "assignment-activation"
    )


def test_compile_routine_activation_rolls_back_schedule_when_assignment_write_fails(
    monkeypatch,
):
    repo = SqliteRoutineRepository()
    command = RoutineActivationCommand(
        id="routine-atomic",
        name="Routine Atomic",
        start_date="2026-03-02",
        status="active",
        tags=["training"],
        notes="Atomic fixture",
        source_artifact_id="artifact-routine-atomic",
        assignments=[
            RoutineActivationAssignment(
                id="assignment-atomic-1",
                card_template_id="card-atomic-1",
                day=1,
                slot="morning",
                position=10,
                prescription_override_json={},
            ),
            RoutineActivationAssignment(
                id="assignment-atomic-2",
                card_template_id="card-atomic-2",
                day=2,
                slot="evening",
                position=20,
                prescription_override_json={},
            ),
        ],
    )
    original_save = routine_db._save_json_record_in_connection
    assignment_write_calls = 0

    def fail_on_second_assignment_write(*args, **kwargs):
        nonlocal assignment_write_calls
        if args[1] == "routine_assignments":
            assignment_write_calls += 1
            if assignment_write_calls == 2:
                raise RuntimeError("simulated assignment failure")
        return original_save(*args, **kwargs)

    monkeypatch.setattr(
        routine_db,
        "_save_json_record_in_connection",
        fail_on_second_assignment_write,
    )

    with pytest.raises(RuntimeError, match="simulated assignment failure"):
        compile_routine_activation(
            repo,
            command,
            activate_card_template_dependency=lambda *_args: None,
        )

    assert load_routine_schedule("routine-atomic") is None
    assert load_routine_assignments(routine_id="routine-atomic") == []
