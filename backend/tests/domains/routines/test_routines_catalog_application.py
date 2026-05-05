"""Tests for routines catalog use cases."""

from contextlib import contextmanager

import pytest

import app.infra.database as db
from app.domains.artifacts.application.artifacts import (
    activate_assistant_artifact,
    create_assistant_artifact,
)
from app.domains.routines.application.catalog import (
    get_routine,
    list_routine_assignments,
    list_routines,
)
from app.domains.routines.infra.sqlite_repository import SqliteRoutineRepository
from app.models import AssistantArtifactCreateRequest, RoutineAssignment, RoutineSchedule


def _card_request(card_id: str) -> AssistantArtifactCreateRequest:
    return AssistantArtifactCreateRequest(
        id=f"artifact-{card_id}",
        kind="card_template",
        schema_version=1,
        payload_json={
            "id": card_id,
            "name": f"Card {card_id}",
            "renderer": "timer_session",
            "slot_default": "morning",
            "summary": "Catalog fixture card",
            "tags": ["training"],
            "payload": {
                "duration_minutes": 10,
                "pattern": "5s in / 5s out",
                "instructions": "Stay relaxed.",
            },
        },
    )


def _routine_request(
    routine_id: str,
    *,
    card_id: str,
) -> AssistantArtifactCreateRequest:
    return AssistantArtifactCreateRequest(
        id=f"artifact-{routine_id}",
        kind="routine_spec",
        schema_version=1,
        payload_json={
            "id": routine_id,
            "name": f"Routine {routine_id}",
            "start_date": "2026-03-02",
            "status": "active",
            "tags": ["training"],
            "notes": "Catalog fixture",
            "assignments": [
                {
                    "id": f"{routine_id}-assignment",
                    "card_template_id": card_id,
                    "day": 1,
                    "slot": "morning",
                    "position": 10,
                    "prescription_override_json": {},
                }
            ],
        },
    )


def _live_routine(routine_id: str) -> RoutineSchedule:
    return RoutineSchedule(
        id=routine_id,
        name=f"Routine {routine_id}",
        start_date="2026-03-02",
        status="active",
        tags=["training"],
        notes="Catalog fixture",
    )


def _assignment(assignment_id: str, *, routine_id: str) -> RoutineAssignment:
    return RoutineAssignment(
        id=assignment_id,
        routine_id=routine_id,
        card_template_id="card-catalog",
        date="2026-03-02",
        slot="morning",
        position=10,
        prescription_override_json={},
    )


def test_list_routines_reads_live_schedules():
    repo = SqliteRoutineRepository()
    repo.save_routine(_live_routine("routine-active"))
    repo.save_routine(_live_routine("routine-paused").model_copy(update={"status": "paused"}))

    response = list_routines(repo, status="active")

    assert [routine.id for routine in response.routines] == ["routine-active"]


def test_get_routine_and_assignments_read_same_routine():
    repo = SqliteRoutineRepository()
    card_artifact = create_assistant_artifact(_card_request("card-catalog"))
    activate_assistant_artifact(card_artifact.id)
    artifact = create_assistant_artifact(
        _routine_request("routine-catalog", card_id="card-catalog")
    )
    activate_assistant_artifact(artifact.id)

    routine = get_routine(repo, "routine-catalog")
    assignments = list_routine_assignments(repo, "routine-catalog")

    assert routine.id == "routine-catalog"
    assert assignments.assignments[0].routine_id == "routine-catalog"


def test_get_routine_raises_lookup_error_for_missing_routine():
    repo = SqliteRoutineRepository()

    with pytest.raises(LookupError, match="Routine missing-routine not found"):
        get_routine(repo, "missing-routine")


def test_list_routine_assignments_raises_lookup_error_for_missing_routine():
    repo = SqliteRoutineRepository()

    with pytest.raises(LookupError, match="Routine missing-routine not found"):
        list_routine_assignments(repo, "missing-routine")


def test_replace_assignments_rolls_back_when_a_write_fails(monkeypatch):
    repo = SqliteRoutineRepository()
    repo.save_routine(_live_routine("routine-atomic"))
    db.save_routine_assignment(_assignment("existing-assignment", routine_id="routine-atomic"))
    original_save = db._save_json_record_in_connection
    save_calls = 0

    def fail_on_second_assignment_write(*args, **kwargs):
        nonlocal save_calls
        if args[1] == "routine_assignments":
            save_calls += 1
            if save_calls == 2:
                raise RuntimeError("simulated write failure")
        return original_save(*args, **kwargs)

    monkeypatch.setattr(db, "_save_json_record_in_connection", fail_on_second_assignment_write)

    with pytest.raises(RuntimeError, match="simulated write failure"):
        repo.replace_assignments(
            routine_id="routine-atomic",
            assignments=[
                _assignment("new-assignment-1", routine_id="routine-atomic"),
                _assignment("new-assignment-2", routine_id="routine-atomic"),
            ],
        )

    assert [item.id for item in db.load_routine_assignments("routine-atomic")] == [
        "existing-assignment"
    ]


def test_replace_assignments_rejects_assignments_for_other_routines():
    repo = SqliteRoutineRepository()
    repo.save_routine(_live_routine("routine-guard"))
    db.save_routine_assignment(_assignment("existing-assignment", routine_id="routine-guard"))

    with pytest.raises(ValueError, match="routine_id"):
        repo.replace_assignments(
            routine_id="routine-guard",
            assignments=[_assignment("wrong-routine-assignment", routine_id="other-routine")],
        )

    assert [item.id for item in db.load_routine_assignments("routine-guard")] == [
        "existing-assignment"
    ]


def test_replace_assignments_rejects_assignment_ids_owned_by_other_routines():
    repo = SqliteRoutineRepository()
    repo.save_routine(_live_routine("routine-target"))
    repo.save_routine(_live_routine("routine-owner"))
    db.save_routine_assignment(_assignment("target-existing", routine_id="routine-target"))
    db.save_routine_assignment(_assignment("shared-assignment", routine_id="routine-owner"))

    with pytest.raises(ValueError, match="already belongs to routine routine-owner"):
        repo.replace_assignments(
            routine_id="routine-target",
            assignments=[_assignment("shared-assignment", routine_id="routine-target")],
        )

    assert [item.id for item in db.load_routine_assignments("routine-target")] == [
        "target-existing"
    ]
    owner_assignments = db.load_routine_assignments("routine-owner")
    assert [item.id for item in owner_assignments] == ["shared-assignment"]
    assert owner_assignments[0].routine_id == "routine-owner"


def test_replace_assignments_replaces_existing_assignments_for_target_routine():
    repo = SqliteRoutineRepository()
    repo.save_routine(_live_routine("routine-replace"))
    db.save_routine_assignment(_assignment("old-assignment-1", routine_id="routine-replace"))
    db.save_routine_assignment(_assignment("old-assignment-2", routine_id="routine-replace"))

    repo.replace_assignments(
        routine_id="routine-replace",
        assignments=[
            _assignment("new-assignment-1", routine_id="routine-replace"),
            _assignment("new-assignment-2", routine_id="routine-replace"),
        ],
    )

    assert [item.id for item in db.load_routine_assignments("routine-replace")] == [
        "new-assignment-1",
        "new-assignment-2",
    ]


def test_replace_routine_assignments_begins_transaction_before_ownership_query(monkeypatch):
    repo = SqliteRoutineRepository()
    repo.save_routine(_live_routine("routine-target"))
    db.save_routine_assignment(_assignment("target-existing", routine_id="routine-target"))
    original_connect = db._connect
    executed_sql: list[str] = []

    class SpyConnection:
        def __init__(self, con):
            self._con = con

        def execute(self, sql: str, params=()):
            executed_sql.append(sql)
            return self._con.execute(sql, params)

        def __getattr__(self, name):
            return getattr(self._con, name)

    @contextmanager
    def spy_connect():
        with original_connect() as con:
            yield SpyConnection(con)

    monkeypatch.setattr(db, "_connect", spy_connect)

    db.replace_routine_assignments(
        "routine-target",
        [_assignment("new-assignment", routine_id="routine-target")],
    )

    assert executed_sql[0] == "BEGIN IMMEDIATE"
    assert executed_sql[1].startswith("SELECT id, routine_id FROM routine_assignments WHERE id IN")
    assert executed_sql[2] == "DELETE FROM routine_assignments WHERE routine_id = ?"
