"""Dependency container for migrated domain slices."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.bootstrap.coach_measurement_port import CoachMeasurementAssessmentPort
from app.bootstrap.run_activity_port import GarminRunActivityPort
from app.core.config import AppConfig, get_app_config
from app.core.profile.adapters import SqliteProfileRepository
from app.domains.artifacts.adapters import SqliteArtifactRepository
from app.domains.coach.adapters import SqliteCoachRepository
from app.domains.coach.application.handlers import CoachHandlers
from app.domains.coach.application.jobs import CoachJobs
from app.domains.coach.application.worker import CoachWorker
from app.domains.coach.read_gateway import CoachReadGateway
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
from app.realtime.events import event_bus


@dataclass(frozen=True)
class AppContainer:
    config: AppConfig
    artifacts_repo: SqliteArtifactRepository
    coach_repo: SqliteCoachRepository
    coach_gateway: CoachReadGateway
    coach_jobs: CoachJobs
    coach_handlers: CoachHandlers
    coach_worker: CoachWorker
    garmin_biometrics_repo: SqliteBiometricRepository
    garmin_runs_repo: SqliteRunsRepository
    journal_repo: SqliteJournalRepository
    profile_repo: SqliteProfileRepository
    programs_repo: SqliteProgramRepository
    routines_repo: SqliteRoutineRepository
    training_repo: SqliteTrainingRepository
    training_run_activity_port: GarminRunActivityPort
    training_measurement_assessment_port: CoachMeasurementAssessmentPort
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
    training_repo = SqliteTrainingRepository()
    training_run_activity_port = GarminRunActivityPort(garmin_runs_repo)
    coach_repo = SqliteCoachRepository()
    training_measurement_assessment_port = CoachMeasurementAssessmentPort(coach_repo)
    coach_gateway = CoachReadGateway(
        runs_repo=garmin_runs_repo,
        biometrics_repo=garmin_biometrics_repo,
        training_repo=training_repo,
        run_activity_port=training_run_activity_port,
        journal_repo=journal_repo,
    )
    coach_jobs = CoachJobs(repo=coach_repo, gateway=coach_gateway)
    coach_root = config.database_path.parent / "coach"
    coach_handlers = CoachHandlers(
        repo=coach_repo,
        gateway=coach_gateway,
        workspace_root=coach_root / "workspaces",
        plot_cache_dir=coach_root / "plots",
        threads_dir=coach_root / "threads",
        logs_dir=coach_root / "logs",
    )
    coach_worker = CoachWorker(
        repo=coach_repo,
        handlers=coach_handlers,
        jobs=coach_jobs,
        broadcast=event_bus.broadcast,
    )
    experiments_read_source = ExperimentReadSource(
        biometric_repo=garmin_biometrics_repo,
        journal_repo=journal_repo,
    )
    garmin_sync_infra = build_garmin_sync_infra(
        config,
        after_successful_sync=coach_jobs.reconcile_pending,
    )
    return AppContainer(
        config=config,
        artifacts_repo=SqliteArtifactRepository(),
        coach_repo=coach_repo,
        coach_gateway=coach_gateway,
        coach_jobs=coach_jobs,
        coach_handlers=coach_handlers,
        coach_worker=coach_worker,
        garmin_biometrics_repo=garmin_biometrics_repo,
        garmin_runs_repo=garmin_runs_repo,
        journal_repo=journal_repo,
        profile_repo=profile_repo,
        programs_repo=SqliteProgramRepository(),
        routines_repo=routines_repo,
        training_repo=training_repo,
        training_run_activity_port=training_run_activity_port,
        training_measurement_assessment_port=training_measurement_assessment_port,
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
