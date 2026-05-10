"""SQLite-backed program repository adapter.

This module is the persistence boundary for imported program specs and version
history. It owns program-specific CRUD while shared SQLite connection and JSON
record primitives remain in `app.infra`.
"""

from __future__ import annotations

from app.domains.programs.contracts import (
    Program,
    ProgramStatus,
    ProgramVersion,
)
from app.infra.jsonstore import JsonStore
from app.infra.jsonstore import model_from_row as _model_from_row
from app.infra.sqlite import connect
from app.utils.timeutil import now_iso

_STORE = JsonStore({"programs"})


def save_program(program: Program) -> None:
    """Persist the current record for one imported program."""
    _STORE.save("programs", program.id, program.model_dump_json())


def load_program(program_id: str) -> Program | None:
    """Load one imported program by id."""
    return _STORE.load("programs", Program, program_id)


def load_programs(status: ProgramStatus | None = None) -> list[Program]:
    """Load imported programs, optionally filtered by lifecycle status."""
    where_sql = ""
    params: tuple[object, ...] = ()
    if status is not None:
        where_sql = "json_extract(data, '$.status') = ?"
        params = (status,)
    return _STORE.load_many(
        "programs",
        Program,
        where_sql=where_sql,
        params=params,
    )


def load_program_versions(program_id: str) -> list[ProgramVersion]:
    """Load stored prior versions for one program ordered by version number."""
    with connect() as con:
        rows = con.execute(
            "SELECT data, created_at, updated_at FROM program_versions "
            "WHERE program_id = ? ORDER BY version",
            (program_id,),
        ).fetchall()
    return [_model_from_row(ProgramVersion, row) for row in rows]


def save_program_import(
    *,
    program: Program,
    previous_version: ProgramVersion | None,
) -> None:
    """Persist a program import and optional previous version atomically."""
    timestamp = now_iso()
    with connect() as con, con:
        if previous_version is not None:
            con.execute(
                "INSERT OR REPLACE INTO program_versions "
                "(program_id, version, data, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    previous_version.program_id,
                    previous_version.version,
                    previous_version.model_dump_json(),
                    timestamp,
                    timestamp,
                ),
            )

        _STORE.save_in_connection(
            con,
            "programs",
            program.id,
            program.model_dump_json(),
        )


class SqliteProgramRepository:
    """Repository adapter used by program application use cases."""

    def get_program(self, program_id: str) -> Program | None:
        """Load one program definition by id."""
        return load_program(program_id)

    def list_programs(self, *, status: ProgramStatus | None = None) -> list[Program]:
        """Load programs, optionally filtered by lifecycle status."""
        return load_programs(status=status)

    def save_program(self, program: Program) -> None:
        """Persist one current program record."""
        save_program(program)

    def list_program_versions(self, program_id: str) -> list[ProgramVersion]:
        """Load prior versions for one program."""
        return load_program_versions(program_id)

    def save_program_import(
        self,
        *,
        program: Program,
        previous_version: ProgramVersion | None,
    ) -> None:
        """Persist an import transaction for the current and previous versions."""
        save_program_import(
            program=program,
            previous_version=previous_version,
        )
