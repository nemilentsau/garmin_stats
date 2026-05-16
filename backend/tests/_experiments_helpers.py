"""Shared test helpers for experiment workflows."""

from app.domains.experiments.read_sources import ExperimentReadSource
from app.domains.garmin_analytics.adapters import SqliteBiometricRepository
from app.domains.journal.adapters import SqliteJournalRepository


def make_experiment_read_source() -> ExperimentReadSource:
    return ExperimentReadSource(
        biometric_repo=SqliteBiometricRepository(),
        journal_repo=SqliteJournalRepository(),
    )
