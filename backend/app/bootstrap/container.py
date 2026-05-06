"""Dependency container for migrated domain slices."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.core.profile.infra.sqlite_repository import SqliteProfileRepository
from app.domains.artifacts.infra.sqlite_repository import SqliteArtifactRepository
from app.domains.assistant.infra.runtime import ClaudeCodeRuntime
from app.domains.assistant.infra.sqlite_repository import SqliteAssistantRepository
from app.domains.experiments.application.exposure_sync import ExperimentExposureSyncService
from app.domains.experiments.infra.sqlite_repository import SqliteExperimentRepository
from app.domains.garmin_analytics.infra.biometric_repository import (
    SqliteBiometricRepository,
)
from app.domains.garmin_sync.adapters import build_garmin_sync_dependencies
from app.domains.garmin_sync.dependencies import GarminSyncDependencies
from app.domains.journal.infra.sqlite_repository import SqliteJournalRepository
from app.domains.programs.infra.sqlite_repository import SqliteProgramRepository
from app.domains.routines.infra.sqlite_repository import SqliteRoutineRepository


@dataclass(frozen=True)
class AppContainer:
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
    experiments_repo = SqliteExperimentRepository()
    routines_repo = SqliteRoutineRepository()
    return AppContainer(
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
        garmin_sync=build_garmin_sync_dependencies(),
    )
