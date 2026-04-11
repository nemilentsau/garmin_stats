"""Dependency container for migrated domain slices."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from app.domains.assistant.infra.runtime import ClaudeCodeRuntime
from app.domains.assistant.infra.sqlite_repository import SqliteAssistantRepository
from app.domains.routines.infra.sqlite_repository import SqliteRoutineRepository
from app.services.experiment_exposure_sync import ExperimentExposureSyncService


@dataclass(frozen=True)
class AppContainer:
    assistant_repo: SqliteAssistantRepository = field(default_factory=SqliteAssistantRepository)
    assistant_runtime: ClaudeCodeRuntime = field(default_factory=ClaudeCodeRuntime)
    routines_repo: SqliteRoutineRepository = field(default_factory=SqliteRoutineRepository)
    experiment_exposure_sync: ExperimentExposureSyncService = field(
        default_factory=ExperimentExposureSyncService
    )


@lru_cache(maxsize=1)
def build_container() -> AppContainer:
    return AppContainer()
