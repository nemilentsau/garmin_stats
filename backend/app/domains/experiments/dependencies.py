"""Ports consumed by experiment application use cases.

Experiment workflows split durable experiment persistence from read-model inputs
owned by other domains. SQLite details belong in adapter modules; application
use cases receive explicit ports for the data each workflow needs.
"""

from __future__ import annotations

from typing import Protocol

from app.domains.experiments.contracts import (
    Experiment,
    ExperimentAnalysis,
    ExperimentExposure,
)
from app.domains.garmin_health.contracts import DailyMetric
from app.domains.journal.contracts import DailyCheckIn


class ExperimentRepository(Protocol):
    """Persistence port for experiment definitions, exposures, and analyses."""

    def list_experiments(
        self,
        *,
        statuses: tuple[str, ...] | None = None,
    ) -> list[Experiment]: ...

    def get_experiment(self, experiment_id: str) -> Experiment | None: ...

    def experiment_exists(self, experiment_id: str) -> bool: ...

    def save_experiment(self, experiment: Experiment) -> None: ...

    def save_experiment_with_analysis(
        self,
        experiment: Experiment,
        analysis: ExperimentAnalysis | None,
    ) -> None: ...

    def list_all_experiment_analyses(self) -> dict[str, ExperimentAnalysis]: ...

    def get_experiment_analysis(self, experiment_id: str) -> ExperimentAnalysis | None: ...

    def save_experiment_analysis(
        self,
        experiment_id: str,
        analysis: ExperimentAnalysis,
    ) -> None: ...

    def delete_experiment_analysis(self, experiment_id: str) -> None: ...

    def list_experiment_exposures(
        self,
        *,
        experiment_id: str | None = None,
        date: str | None = None,
    ) -> list[ExperimentExposure]: ...

    def save_experiment_exposure(self, exposure: ExperimentExposure) -> None: ...

    def save_experiment_exposure_and_invalidate_analysis(
        self,
        exposure: ExperimentExposure,
    ) -> None: ...


class ExperimentPreviewRepository(Protocol):
    """Minimal persistence port needed to detect duplicate imports."""

    def experiment_exists(self, experiment_id: str) -> bool: ...


class ExperimentPreviewReadSource(Protocol):
    """Read source for validating experiment metric paths and baseline coverage."""

    def list_daily_metrics(self) -> list[DailyMetric]: ...


class ExperimentAnalysisReadSource(ExperimentPreviewReadSource, Protocol):
    """Read source for recomputing experiment analysis inputs."""

    def list_daily_checkins(self) -> list[DailyCheckIn]: ...
