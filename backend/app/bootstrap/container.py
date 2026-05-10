"""Dependency container for migrated domain slices."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.core.config import AppConfig, get_app_config
from app.core.profile.infra.sqlite_repository import SqliteProfileRepository
from app.domains.artifacts.adapters import SqliteArtifactRepository
from app.domains.assistant.infra.runtime import ClaudeCodeRuntime
from app.domains.assistant.infra.sqlite_repository import SqliteAssistantRepository
from app.domains.experiments.adapters import SqliteExperimentRepository
from app.domains.experiments.application.exposure_sync import ExperimentExposureSyncService
from app.domains.garmin_analytics.adapters import (
    SqliteBiometricRepository,
)
from app.domains.garmin_sync.adapters import build_garmin_sync_dependencies
from app.domains.garmin_sync.dependencies import GarminSyncDependencies
from app.domains.journal.infra.sqlite_repository import SqliteJournalRepository
from app.domains.programs.infra.sqlite_repository import SqliteProgramRepository
from app.domains.routines.adapters import SqliteRoutineRepository


@dataclass(frozen=True)
class AppContainer:
    config: AppConfig
    artifacts_repo: SqliteArtifactRepository
    assistant_repo: SqliteAssistantRepository
    assistant_runtime: ClaudeCodeRuntime
    garmin_biometrics_repo: SqliteBiometricRepository
    journal_repo: SqliteJournalRepository
    profile_repo: SqliteProfileRepository
    programs_repo: SqliteProgramRepository
    routines_repo: SqliteRoutineRepository
    experiments_repo: SqliteExperimentRepository
    experiment_exposure_sync: ExperimentExposureSyncService
    garmin_sync: GarminSyncDependencies


@lru_cache(maxsize=1)
def build_container() -> AppContainer:
    config = get_app_config()
    experiments_repo = SqliteExperimentRepository()
    routines_repo = SqliteRoutineRepository()
    return AppContainer(
        config=config,
        artifacts_repo=SqliteArtifactRepository(),
        assistant_repo=SqliteAssistantRepository(experiment_repo=experiments_repo),
        assistant_runtime=ClaudeCodeRuntime(),
        garmin_biometrics_repo=SqliteBiometricRepository(),
        journal_repo=SqliteJournalRepository(),
        profile_repo=SqliteProfileRepository(),
        programs_repo=SqliteProgramRepository(),
        routines_repo=routines_repo,
        experiments_repo=experiments_repo,
        experiment_exposure_sync=ExperimentExposureSyncService(experiments_repo, routines_repo),
        garmin_sync=build_garmin_sync_dependencies(config),
    )
