"""Contracts for imported program specs."""

from __future__ import annotations

from typing import Literal

from app.contracts.base import AutoTotalResponse, DefaultsRequired

ProgramStatus = Literal["active", "retired"]


class Program(DefaultsRequired):
    id: str
    name: str
    version: int
    status: ProgramStatus = "active"
    spec: dict[str, object] = {}
    imported_at: str | None = None
    updated_at: str | None = None
    retired_at: str | None = None


class ProgramVersion(DefaultsRequired):
    program_id: str
    version: int
    spec: dict[str, object] = {}
    imported_at: str | None = None


class ProgramsResponse(AutoTotalResponse, items_field="programs"):
    programs: list[Program] = []
    total: int = 0


class ProgramVersionsResponse(AutoTotalResponse, items_field="versions"):
    versions: list[ProgramVersion] = []
    total: int = 0
