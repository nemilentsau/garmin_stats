"""Program spec HTTP routes."""

from fastapi import APIRouter, HTTPException

from ..models import Program, ProgramsResponse, ProgramVersionsResponse
from ..services.programs import (
    activate_program,
    get_program,
    get_program_versions,
    import_program,
    list_programs,
    retire_program,
)

router = APIRouter(prefix="/api/programs", tags=["programs"])


@router.get("", response_model=ProgramsResponse)
def get_programs(status: str | None = None):
    """Return all programs, optionally filtered by status."""
    return list_programs(status=status)


@router.get("/{program_id}", response_model=Program)
def get_program_detail(program_id: str):
    """Return a single program with its full spec."""
    try:
        return get_program(program_id)
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.post("/import", response_model=Program)
def post_import_program(spec: dict):
    """Import a program spec JSON. Creates/updates program, routines, and experiments."""
    if "program" not in spec:
        raise HTTPException(status_code=400, detail="Missing 'program' key in spec")
    program_info = spec["program"]
    if not program_info.get("id") or not program_info.get("name"):
        raise HTTPException(
            status_code=400,
            detail="Program spec must have 'program.id' and 'program.name'",
        )
    return import_program(spec)


@router.put("/{program_id}/retire", response_model=Program)
def put_retire_program(program_id: str):
    """Set a program's status to retired, preserving all data."""
    try:
        return retire_program(program_id)
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.put("/{program_id}/activate", response_model=Program)
def put_activate_program(program_id: str):
    """Reactivate a retired program."""
    try:
        return activate_program(program_id)
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err


@router.get("/{program_id}/versions", response_model=ProgramVersionsResponse)
def get_versions(program_id: str):
    """Return version history for a program."""
    try:
        return get_program_versions(program_id)
    except LookupError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err
