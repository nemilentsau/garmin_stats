"""Dependency container for migrated domain slices."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from app.domains.routines.infra.sqlite_repository import SqliteRoutineRepository
from app.services.experiment_exposure_sync import ExperimentExposureSyncService


@dataclass(frozen=True)
class AppContainer:
    routines_repo: SqliteRoutineRepository = field(default_factory=SqliteRoutineRepository)
    experiment_exposure_sync: ExperimentExposureSyncService = field(
        default_factory=ExperimentExposureSyncService
    )


@lru_cache(maxsize=1)
def build_container() -> AppContainer:
    return AppContainer()
