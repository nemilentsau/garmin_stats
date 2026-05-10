"""Pydantic contracts owned by the programs domain.

Programs are imported spec snapshots plus lifecycle state and retained version
history. The contracts intentionally stop at program records; activation into
runtime child records belongs to later explicit workflows.
"""

from __future__ import annotations

from typing import Literal

from app.contracts.base import AutoTotalResponse, DefaultsRequired

ProgramStatus = Literal["active", "retired"]


class Program(DefaultsRequired):
    """Current imported program spec and lifecycle state."""

    id: str
    name: str
    version: int
    status: ProgramStatus = "active"
    spec: dict[str, object] = {}
    imported_at: str | None = None
    updated_at: str | None = None
    retired_at: str | None = None


class ProgramVersion(DefaultsRequired):
    """Archived spec snapshot superseded by a later import."""

    program_id: str
    version: int
    spec: dict[str, object] = {}
    imported_at: str | None = None


class ProgramsResponse(AutoTotalResponse, items_field="programs"):
    """List response for imported programs."""

    programs: list[Program] = []


class ProgramVersionsResponse(AutoTotalResponse, items_field="versions"):
    """List response for prior imported program versions."""

    versions: list[ProgramVersion] = []
