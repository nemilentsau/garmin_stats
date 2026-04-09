"""Minimal dependency container for migrated domain slices."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domains.routines.infra.sqlite_repository import SqliteRoutineRepository


@dataclass(frozen=True)
class AppContainer:
    routines_repo: SqliteRoutineRepository = field(default_factory=SqliteRoutineRepository)


def build_container() -> AppContainer:
    return AppContainer()
