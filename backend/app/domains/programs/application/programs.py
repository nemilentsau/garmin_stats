"""Program spec import and management use cases."""

from __future__ import annotations

from typing import cast

from app.models import (
    Experiment,
    OutcomeMetric,
    Program,
    ProgramsResponse,
    ProgramStatus,
    ProgramVersion,
    ProgramVersionsResponse,
    Routine,
)
from app.utils.timeutil import now_iso

from .ports import ProgramRepository

_CORE_LIKE_TYPES = {"core", "supporting"}
_DESCRIPTION_FIELDS: tuple[tuple[str, str | None], ...] = (
    ("target", None),
    ("pattern", None),
    ("cues", None),
    ("full_dose", "Full"),
    ("reduced_dose", "Reduced"),
    ("dose", None),
)


def _protocol_to_routine(program_id: str, protocol: dict[str, object]) -> Routine:
    routine_id = f"{program_id}:{cast(str, protocol['id'])}"

    desc_parts: list[str] = []
    for key, label in _DESCRIPTION_FIELDS:
        value = protocol.get(key)
        if isinstance(value, str) and value:
            desc_parts.append(f"{label}: {value}" if label else value)

    protocol_type = protocol.get("type", "")
    if protocol.get("default_duration_min"):
        unit = "minutes"
    elif protocol.get("default_hold_sec"):
        unit = "seconds"
    elif protocol.get("default_reps"):
        unit = "reps"
    elif protocol_type in _CORE_LIKE_TYPES:
        unit = "sets_x_reps"
    else:
        unit = "boolean"

    category = protocol.get("category", "general")
    if protocol_type in _CORE_LIKE_TYPES:
        category = protocol_type

    tags = protocol.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    return Routine(
        id=routine_id,
        name=cast(str, protocol["name"]),
        category=cast(str, category),
        status="active",
        description=" | ".join(desc_parts) if desc_parts else None,
        default_unit=unit,
        target_frequency=None,
        default_time_of_day=None,
        tags=[f"program:{program_id}", *tags],
        linked_goal_ids=[],
    )


def _spec_experiment_to_model(program_id: str, exp: dict[str, object]) -> Experiment:
    exp_id = f"{program_id}:{cast(str, exp['id'])}"
    linked_protocol_ids = exp.get("linked_protocol_ids", [])
    if not isinstance(linked_protocol_ids, list):
        linked_protocol_ids = []
    outcome_metrics = exp.get("outcome_metrics", [])
    if not isinstance(outcome_metrics, list):
        outcome_metrics = []
    expected_lag_days = exp.get("expected_lag_days", [])
    if not isinstance(expected_lag_days, list):
        expected_lag_days = []
    return Experiment(
        id=exp_id,
        name=cast(str, exp["name"]),
        status="active",
        goal=cast(str | None, exp.get("goal")),
        hypothesis=cast(str | None, exp.get("hypothesis")),
        linked_routine_ids=[f"{program_id}:{pid}" for pid in linked_protocol_ids],
        outcome_metrics=[
            OutcomeMetric(path=m) if isinstance(m, str) else OutcomeMetric(**m)
            for m in outcome_metrics
        ],
        expected_lag_days=expected_lag_days,
    )


def _spec_child_ids(spec: dict[str, object], program_id: str) -> tuple[set[str], set[str]]:
    protocols = spec.get("protocols", [])
    experiments = spec.get("experiments", [])
    if not isinstance(protocols, list):
        protocols = []
    if not isinstance(experiments, list):
        experiments = []
    routine_ids = {
        f"{program_id}:{protocol['id']}"
        for protocol in protocols
        if isinstance(protocol, dict) and isinstance(protocol.get("id"), str)
    }
    experiment_ids = {
        f"{program_id}:{exp['id']}"
        for exp in experiments
        if isinstance(exp, dict) and isinstance(exp.get("id"), str)
    }
    return routine_ids, experiment_ids


def import_program(repo: ProgramRepository, spec: dict[str, object]) -> Program:
    """Import a program spec, creating/updating routines and experiments."""
    program_info = spec.get("program")
    if (
        not isinstance(program_info, dict)
        or not program_info.get("id")
        or not program_info.get("name")
    ):
        raise ValueError("Program spec must have 'program.id' and 'program.name'")
    program_id = str(program_info["id"])
    version = int(program_info["version"])
    now = now_iso()
    protocols = spec.get("protocols", [])
    experiments_spec = spec.get("experiments", [])
    if not isinstance(protocols, list):
        protocols = []
    if not isinstance(experiments_spec, list):
        experiments_spec = []

    routines = [
        _protocol_to_routine(program_id, protocol)
        for protocol in protocols
        if isinstance(protocol, dict)
    ]
    experiments = [
        _spec_experiment_to_model(program_id, exp)
        for exp in experiments_spec
        if isinstance(exp, dict)
    ]

    existing = repo.get_program(program_id)
    existing_routine_ids, existing_experiment_ids = (
        _spec_child_ids(existing.spec, program_id) if existing is not None else (set(), set())
    )
    current_routine_ids = {r.id for r in routines}
    current_experiment_ids = {e.id for e in experiments}

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
    repo.replace_program_import(
        program=program,
        previous_version=previous_version,
        routines=routines,
        experiments=experiments,
        stale_routine_ids=existing_routine_ids - current_routine_ids,
        stale_experiment_ids=existing_experiment_ids - current_experiment_ids,
    )

    return program


def list_programs(
    repo: ProgramRepository, status: ProgramStatus | None = None
) -> ProgramsResponse:
    programs = repo.list_programs(status=status)
    return ProgramsResponse(programs=programs)


def get_program(repo: ProgramRepository, program_id: str) -> Program:
    result = repo.get_program(program_id)
    if result is None:
        raise LookupError(f"Program {program_id} not found")
    return result


def retire_program(repo: ProgramRepository, program_id: str) -> Program:
    program = get_program(repo, program_id)
    program.status = "retired"
    program.retired_at = now_iso()
    repo.save_program(program)
    return program


def activate_program(repo: ProgramRepository, program_id: str) -> Program:
    program = get_program(repo, program_id)
    program.status = "active"
    program.retired_at = None
    repo.save_program(program)
    return program


def get_program_versions(
    repo: ProgramRepository,
    program_id: str,
) -> ProgramVersionsResponse:
    get_program(repo, program_id)
    versions = repo.list_program_versions(program_id)
    return ProgramVersionsResponse(versions=versions)
