"""Dependency container for migrated domain slices."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.bootstrap.run_activity_port import GarminRunActivityPort
from app.core.config import AppConfig, get_app_config
from app.core.profile.adapters import SqliteProfileRepository
from app.domains.artifacts.adapters import SqliteArtifactRepository
from app.domains.assistant.adapters import SqliteAssistantRepository
from app.domains.assistant.read_gateway import AssistantReadModelGateway
from app.domains.assistant.runtime import ClaudeCodeRuntime
from app.domains.experiments.adapters import SqliteExperimentRepository
from app.domains.experiments.application.exposure_sync import ExperimentExposureSyncService
from app.domains.experiments.read_sources import ExperimentReadSource
from app.domains.garmin_analytics.adapters import (
    SqliteBiometricRepository,
    SqliteRunsRepository,
)
from app.domains.garmin_sync.dependencies import GarminSyncDependencies
from app.domains.garmin_sync.infra.factory import build_garmin_sync_infra
from app.domains.garmin_sync.infra.watcher import DataDirectoryWatcher
from app.domains.journal.adapters import SqliteJournalRepository
from app.domains.programs.adapters import SqliteProgramRepository
from app.domains.routines.adapters import SqliteRoutineRepository
from app.domains.training.adapters import SqliteTrainingRepository


@dataclass(frozen=True)
class AppContainer:
    config: AppConfig
    artifacts_repo: SqliteArtifactRepository
    assistant_repo: SqliteAssistantRepository
    assistant_read_store: AssistantReadModelGateway
    assistant_runtime: ClaudeCodeRuntime
    garmin_biometrics_repo: SqliteBiometricRepository
    garmin_runs_repo: SqliteRunsRepository
    journal_repo: SqliteJournalRepository
    profile_repo: SqliteProfileRepository
    programs_repo: SqliteProgramRepository
    routines_repo: SqliteRoutineRepository
    training_repo: SqliteTrainingRepository
    training_run_activity_port: GarminRunActivityPort
    experiments_repo: SqliteExperimentRepository
    experiments_read_source: ExperimentReadSource
    experiment_exposure_sync: ExperimentExposureSyncService
    garmin_sync: GarminSyncDependencies
    garmin_sync_watcher: DataDirectoryWatcher


@lru_cache(maxsize=1)
def build_container() -> AppContainer:
    config = get_app_config()
    experiments_repo = SqliteExperimentRepository()
    routines_repo = SqliteRoutineRepository()
    profile_repo = SqliteProfileRepository()
    garmin_biometrics_repo = SqliteBiometricRepository()
    garmin_runs_repo = SqliteRunsRepository()
    journal_repo = SqliteJournalRepository()
    experiments_read_source = ExperimentReadSource(
        biometric_repo=garmin_biometrics_repo,
        journal_repo=journal_repo,
    )
    garmin_sync_infra = build_garmin_sync_infra(config)
    return AppContainer(
        config=config,
        artifacts_repo=SqliteArtifactRepository(),
        assistant_repo=SqliteAssistantRepository(),
        assistant_read_store=AssistantReadModelGateway(
            experiment_repo=experiments_repo,
            experiment_read_source=experiments_read_source,
            profile_repo=profile_repo,
            routine_repo=routines_repo,
            journal_repo=journal_repo,
            biometric_repo=garmin_biometrics_repo,
        ),
        assistant_runtime=ClaudeCodeRuntime(),
        garmin_biometrics_repo=garmin_biometrics_repo,
        garmin_runs_repo=garmin_runs_repo,
        journal_repo=journal_repo,
        profile_repo=profile_repo,
        programs_repo=SqliteProgramRepository(),
        routines_repo=routines_repo,
        training_repo=SqliteTrainingRepository(),
        training_run_activity_port=GarminRunActivityPort(garmin_runs_repo),
        experiments_repo=experiments_repo,
        experiments_read_source=experiments_read_source,
        experiment_exposure_sync=ExperimentExposureSyncService(
            experiments_repo,
            experiments_read_source,
            routines_repo,
        ),
        garmin_sync=garmin_sync_infra.dependencies,
        garmin_sync_watcher=garmin_sync_infra.watcher,
    )
