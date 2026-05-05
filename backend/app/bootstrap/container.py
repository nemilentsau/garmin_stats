"""Dependency container for migrated domain slices."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from app.domains.assistant.infra.runtime import ClaudeCodeRuntime
from app.domains.assistant.infra.sqlite_repository import SqliteAssistantRepository
from app.domains.experiments.application.exposure_sync import ExperimentExposureSyncService
from app.domains.garmin_analytics.infra.biometric_repository import (
    SqliteBiometricRepository,
)
from app.domains.routines.infra.sqlite_repository import SqliteRoutineRepository


@dataclass(frozen=True)
class AppContainer:
    assistant_repo: SqliteAssistantRepository = field(default_factory=SqliteAssistantRepository)
    assistant_runtime: ClaudeCodeRuntime = field(default_factory=ClaudeCodeRuntime)
    garmin_biometrics_repo: SqliteBiometricRepository = field(
        default_factory=SqliteBiometricRepository
    )
    routines_repo: SqliteRoutineRepository = field(default_factory=SqliteRoutineRepository)
    experiment_exposure_sync: ExperimentExposureSyncService = field(
        default_factory=ExperimentExposureSyncService
    )


@lru_cache(maxsize=1)
def build_container() -> AppContainer:
    return AppContainer()
