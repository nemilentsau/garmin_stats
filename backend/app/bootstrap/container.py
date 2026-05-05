"""Dependency container for migrated domain slices."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.core.profile.infra.sqlite_repository import SqliteProfileRepository
from app.domains.assistant.infra.runtime import ClaudeCodeRuntime
from app.domains.assistant.infra.sqlite_repository import SqliteAssistantRepository
from app.domains.experiments.application.exposure_sync import ExperimentExposureSyncService
from app.domains.experiments.infra.sqlite_repository import SqliteExperimentRepository
from app.domains.garmin_analytics.infra.biometric_repository import (
    SqliteBiometricRepository,
)
from app.domains.journal.infra.sqlite_repository import SqliteJournalRepository
from app.domains.routines.infra.sqlite_repository import SqliteRoutineRepository


@dataclass(frozen=True)
class AppContainer:
    assistant_repo: SqliteAssistantRepository
    assistant_runtime: ClaudeCodeRuntime
    garmin_biometrics_repo: SqliteBiometricRepository
    journal_repo: SqliteJournalRepository
    profile_repo: SqliteProfileRepository
    routines_repo: SqliteRoutineRepository
    experiments_repo: SqliteExperimentRepository
    experiment_exposure_sync: ExperimentExposureSyncService


@lru_cache(maxsize=1)
def build_container() -> AppContainer:
    experiments_repo = SqliteExperimentRepository()
    routines_repo = SqliteRoutineRepository()
    return AppContainer(
        assistant_repo=SqliteAssistantRepository(),
        assistant_runtime=ClaudeCodeRuntime(),
        garmin_biometrics_repo=SqliteBiometricRepository(),
        journal_repo=SqliteJournalRepository(),
        profile_repo=SqliteProfileRepository(),
        routines_repo=routines_repo,
        experiments_repo=experiments_repo,
        experiment_exposure_sync=ExperimentExposureSyncService(experiments_repo, routines_repo),
    )
