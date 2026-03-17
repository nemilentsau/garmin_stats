"""Program spec import and management service."""

from datetime import UTC, datetime

from ..infra.database import (
    delete_experiment,
    delete_routine,
    load_program,
    load_program_versions,
    load_programs,
    save_experiment,
    save_program,
    save_program_version,
    save_routine,
)
from ..models import (
    Experiment,
    Program,
    ProgramsResponse,
    ProgramVersion,
    ProgramVersionsResponse,
    Routine,
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _protocol_to_routine(program_id: str, protocol: dict) -> Routine:
    """Convert a program spec protocol entry to a Routine model."""
    pid = protocol["id"]
    routine_id = f"{program_id}:{pid}"

    # Build description from available fields
    desc_parts: list[str] = []
    if protocol.get("target"):
        desc_parts.append(protocol["target"])
    if protocol.get("pattern"):
        desc_parts.append(protocol["pattern"])
    if protocol.get("cues"):
        desc_parts.append(protocol["cues"])
    if protocol.get("full_dose"):
        desc_parts.append(f"Full: {protocol['full_dose']}")
    if protocol.get("reduced_dose"):
        desc_parts.append(f"Reduced: {protocol['reduced_dose']}")
    if protocol.get("dose"):
        desc_parts.append(protocol["dose"])

    # Determine default_unit
    ptype = protocol.get("type", "")
    if protocol.get("default_duration_min"):
        unit = "minutes"
    elif protocol.get("default_hold_sec"):
        unit = "seconds"
    elif protocol.get("default_reps"):
        unit = "reps"
    elif ptype in ("core", "supporting"):
        unit = "sets_x_reps"
    else:
        unit = "boolean"

    # Use protocol type as category when more specific (core, supporting)
    category = protocol.get("category", "general")
    if ptype in ("core", "supporting"):
        category = ptype

    return Routine(
        id=routine_id,
        name=protocol["name"],
        category=category,
        status="active",
        description=" | ".join(desc_parts) if desc_parts else None,
        default_unit=unit,
        target_frequency=None,
        default_time_of_day=None,
        tags=[f"program:{program_id}", *protocol.get("tags", [])],
        linked_goal_ids=[],
    )


def _spec_experiment_to_model(program_id: str, exp: dict) -> Experiment:
    """Convert a program spec experiment entry to an Experiment model."""
    exp_id = f"{program_id}:{exp['id']}"
    linked_routine_ids = [
        f"{program_id}:{pid}" for pid in exp.get("linked_protocol_ids", [])
    ]
    return Experiment(
        id=exp_id,
        name=exp["name"],
        status="active",
        goal=exp.get("goal"),
        hypothesis=exp.get("hypothesis"),
        linked_routine_ids=linked_routine_ids,
        outcome_metrics=exp.get("outcome_metrics", []),
        expected_lag_days=exp.get("expected_lag_days", []),
    )


def _spec_child_ids(spec: dict, program_id: str) -> tuple[set[str], set[str]]:
    routine_ids = {
        f"{program_id}:{protocol['id']}"
        for protocol in spec.get("protocols", [])
        if isinstance(protocol, dict) and isinstance(protocol.get("id"), str)
    }
    experiment_ids = {
        f"{program_id}:{exp['id']}"
        for exp in spec.get("experiments", [])
        if isinstance(exp, dict) and isinstance(exp.get("id"), str)
    }
    return routine_ids, experiment_ids


def import_program(spec: dict) -> Program:
    """Import a program spec, creating/updating routines and experiments."""
    program_info = spec["program"]
    program_id: str = program_info["id"]
    version: int = program_info["version"]
    now = _now_iso()

    existing = load_program(program_id)
    existing_routine_ids, existing_experiment_ids = (
        _spec_child_ids(existing.spec, program_id) if existing is not None else (set(), set())
    )
    current_routine_ids, current_experiment_ids = _spec_child_ids(spec, program_id)

    # Archive current version before overwriting
    if existing is not None:
        save_program_version(ProgramVersion(
            program_id=existing.id,
            version=existing.version,
            spec=existing.spec,
            imported_at=existing.imported_at,
        ))

    # Create/update the program record
    program = Program(
        id=program_id,
        name=program_info["name"],
        version=version,
        status=existing.status if existing else "active",
        spec=spec,
        imported_at=existing.imported_at if existing else now,
        updated_at=now,
        retired_at=existing.retired_at if existing else None,
    )
    save_program(program)

    # Create routines from protocols
    for protocol in spec.get("protocols", []):
        routine = _protocol_to_routine(program_id, protocol)
        save_routine(routine)

    # Create experiments
    for exp in spec.get("experiments", []):
        experiment = _spec_experiment_to_model(program_id, exp)
        save_experiment(experiment)

    for routine_id in sorted(existing_routine_ids - current_routine_ids):
        delete_routine(routine_id)
    for experiment_id in sorted(existing_experiment_ids - current_experiment_ids):
        delete_experiment(experiment_id)

    return program


def list_programs(status: str | None = None) -> ProgramsResponse:
    """Return all programs, optionally filtered by status."""
    programs = load_programs(status=status)
    return ProgramsResponse(programs=programs, total=len(programs))


def get_program(program_id: str) -> Program:
    """Load a single program."""
    result = load_program(program_id)
    if result is None:
        raise LookupError(f"Program {program_id} not found")
    return result


def retire_program(program_id: str) -> Program:
    """Set a program's status to retired."""
    program = get_program(program_id)
    program.status = "retired"
    program.retired_at = _now_iso()
    save_program(program)
    return program


def activate_program(program_id: str) -> Program:
    """Reactivate a retired program."""
    program = get_program(program_id)
    program.status = "active"
    program.retired_at = None
    save_program(program)
    return program


def get_program_versions(program_id: str) -> ProgramVersionsResponse:
    """Return version history for a program."""
    # Ensure program exists
    get_program(program_id)
    versions = load_program_versions(program_id)
    return ProgramVersionsResponse(versions=versions, total=len(versions))
