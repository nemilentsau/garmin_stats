"""Tests for routines catalog use cases."""

from contextlib import contextmanager

import pytest

import app.domains.routines.adapters as routine_db
from app.domains.routines.adapters import SqliteRoutineRepository
from app.domains.routines.application.catalog import (
    get_routine,
    list_routine_assignments,
    list_routines,
)
from tests._routines_helpers import (
    activate_routine_card,
    activate_routine_spec,
    routine_assignment_spec,
)
from tests._routines_helpers import (
    live_routine as _live_routine,
)
from tests._routines_helpers import (
    live_routine_assignment as _assignment,
)


def test_list_routines_reads_live_schedules():
    repo = SqliteRoutineRepository()
    repo.save_routine(_live_routine("routine-active"))
    repo.save_routine(_live_routine("routine-paused").model_copy(update={"status": "paused"}))

    response = list_routines(repo, status="active")

    assert [routine.id for routine in response.routines] == ["routine-active"]


def test_get_routine_and_assignments_read_same_routine():
    repo = SqliteRoutineRepository()
    activate_routine_card("card-catalog")
    activate_routine_spec(
        "routine-catalog",
        assignments=[
            routine_assignment_spec(
                "routine-catalog-assignment",
                card_template_id="card-catalog",
            )
        ],
    )

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
    routine_db.save_routine_assignment(
        _assignment("existing-assignment", routine_id="routine-atomic")
    )
    original_save = routine_db._save_json_record_in_connection
    save_calls = 0

    def fail_on_second_assignment_write(*args, **kwargs):
        nonlocal save_calls
        if args[1] == "routine_assignments":
            save_calls += 1
            if save_calls == 2:
                raise RuntimeError("simulated write failure")
        return original_save(*args, **kwargs)

    monkeypatch.setattr(
        routine_db, "_save_json_record_in_connection", fail_on_second_assignment_write
    )

    with pytest.raises(RuntimeError, match="simulated write failure"):
        repo.replace_assignments(
            routine_id="routine-atomic",
            assignments=[
                _assignment("new-assignment-1", routine_id="routine-atomic"),
                _assignment("new-assignment-2", routine_id="routine-atomic"),
            ],
        )

    assert [item.id for item in routine_db.load_routine_assignments("routine-atomic")] == [
        "existing-assignment"
    ]


def test_replace_assignments_rejects_assignments_for_other_routines():
    repo = SqliteRoutineRepository()
    repo.save_routine(_live_routine("routine-guard"))
    routine_db.save_routine_assignment(
        _assignment("existing-assignment", routine_id="routine-guard")
    )

    with pytest.raises(ValueError, match="routine_id"):
        repo.replace_assignments(
            routine_id="routine-guard",
            assignments=[_assignment("wrong-routine-assignment", routine_id="other-routine")],
        )

    assert [item.id for item in routine_db.load_routine_assignments("routine-guard")] == [
        "existing-assignment"
    ]


def test_replace_assignments_rejects_assignment_ids_owned_by_other_routines():
    repo = SqliteRoutineRepository()
    repo.save_routine(_live_routine("routine-target"))
    repo.save_routine(_live_routine("routine-owner"))
    routine_db.save_routine_assignment(_assignment("target-existing", routine_id="routine-target"))
    routine_db.save_routine_assignment(_assignment("shared-assignment", routine_id="routine-owner"))

    with pytest.raises(ValueError, match="already belongs to routine routine-owner"):
        repo.replace_assignments(
            routine_id="routine-target",
            assignments=[_assignment("shared-assignment", routine_id="routine-target")],
        )

    assert [item.id for item in routine_db.load_routine_assignments("routine-target")] == [
        "target-existing"
    ]
    owner_assignments = routine_db.load_routine_assignments("routine-owner")
    assert [item.id for item in owner_assignments] == ["shared-assignment"]
    assert owner_assignments[0].routine_id == "routine-owner"


def test_replace_assignments_replaces_existing_assignments_for_target_routine():
    repo = SqliteRoutineRepository()
    repo.save_routine(_live_routine("routine-replace"))
    routine_db.save_routine_assignment(
        _assignment("old-assignment-1", routine_id="routine-replace")
    )
    routine_db.save_routine_assignment(
        _assignment("old-assignment-2", routine_id="routine-replace")
    )

    repo.replace_assignments(
        routine_id="routine-replace",
        assignments=[
            _assignment("new-assignment-1", routine_id="routine-replace"),
            _assignment("new-assignment-2", routine_id="routine-replace"),
        ],
    )

    assert [item.id for item in routine_db.load_routine_assignments("routine-replace")] == [
        "new-assignment-1",
        "new-assignment-2",
    ]


def test_replace_routine_assignments_begins_transaction_before_ownership_query(monkeypatch):
    repo = SqliteRoutineRepository()
    repo.save_routine(_live_routine("routine-target"))
    routine_db.save_routine_assignment(_assignment("target-existing", routine_id="routine-target"))
    original_connect = routine_db.connect
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

    monkeypatch.setattr(routine_db, "connect", spy_connect)

    routine_db.replace_routine_assignments(
        "routine-target",
        [_assignment("new-assignment", routine_id="routine-target")],
    )

    assert executed_sql[0] == "BEGIN IMMEDIATE"
    assert executed_sql[1].startswith("SELECT id, routine_id FROM routine_assignments WHERE id IN")
    assert executed_sql[2] == "DELETE FROM routine_assignments WHERE routine_id = ?"
