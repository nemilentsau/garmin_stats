"""Program spec import and lifecycle use cases.

Programs currently persist imported specs, active/retired status, and prior
version snapshots only. This application layer deliberately does not activate
protocols, routines, experiments, or artifact records; those future workflows
will enter through explicit dependencies instead of hidden side effects.
"""

from __future__ import annotations

from app.domains.programs.contracts import (
    Program,
    ProgramsResponse,
    ProgramStatus,
    ProgramVersion,
    ProgramVersionsResponse,
)
from app.domains.programs.dependencies import ProgramRepository
from app.utils.timeutil import now_iso


def import_program(repo: ProgramRepository, spec: dict[str, object]) -> Program:
    """Import a placeholder program spec without activating child records."""
    if "program" not in spec:
        raise ValueError("Missing 'program' key in spec")
    program_info = spec["program"]
    if (
        not isinstance(program_info, dict)
        or not program_info.get("id")
        or not program_info.get("name")
    ):
        raise ValueError("Program spec must have 'program.id' and 'program.name'")
    try:
        version = int(program_info["version"])
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError("Program spec must include numeric 'program.version'") from e
    program_id = str(program_info["id"])
    now = now_iso()

    existing = repo.get_program(program_id)

    previous_version = (
        ProgramVersion(
            program_id=existing.id,
            version=existing.version,
            spec=existing.spec,
            imported_at=existing.imported_at,
        )
        if existing is not None
        else None
    )

    program = Program(
        id=program_id,
        name=str(program_info["name"]),
        version=version,
        status=existing.status if existing else "active",
        spec=spec,
        imported_at=existing.imported_at if existing else now,
        updated_at=now,
        retired_at=existing.retired_at if existing else None,
    )
    repo.save_program_import(
        program=program,
        previous_version=previous_version,
    )

    return program


def list_programs(
    repo: ProgramRepository, status: ProgramStatus | None = None
) -> ProgramsResponse:
    """List imported programs, optionally filtered by lifecycle status."""
    programs = repo.list_programs(status=status)
    return ProgramsResponse(programs=programs)


def get_program(repo: ProgramRepository, program_id: str) -> Program:
    """Return one imported program or raise when it does not exist."""
    result = repo.get_program(program_id)
    if result is None:
        raise LookupError(f"Program {program_id} not found")
    return result


def retire_program(repo: ProgramRepository, program_id: str) -> Program:
    """Mark one imported program retired without deleting version history."""
    program = get_program(repo, program_id)
    program.status = "retired"
    program.retired_at = now_iso()
    repo.save_program(program)
    return program


def activate_program(repo: ProgramRepository, program_id: str) -> Program:
    """Reactivate one imported program while preserving its import history."""
    program = get_program(repo, program_id)
    program.status = "active"
    program.retired_at = None
    repo.save_program(program)
    return program


def get_program_versions(
    repo: ProgramRepository,
    program_id: str,
) -> ProgramVersionsResponse:
    """Return prior versions for an existing imported program."""
    get_program(repo, program_id)
    versions = repo.list_program_versions(program_id)
    return ProgramVersionsResponse(versions=versions)
