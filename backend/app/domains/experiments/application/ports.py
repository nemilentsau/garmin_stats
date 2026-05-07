"""Repository contracts for experiment use cases."""

from __future__ import annotations

from typing import Protocol

from app.domains.garmin_analytics.contracts import DailyMetric
from app.models import (
    DailyCheckIn,
    Experiment,
    ExperimentAnalysis,
    ExperimentExposure,
)


class ExperimentRepository(Protocol):
    def list_experiments(
        self,
        *,
        statuses: tuple[str, ...] | None = None,
    ) -> list[Experiment]: ...

    def get_experiment(self, experiment_id: str) -> Experiment | None: ...

    def experiment_exists(self, experiment_id: str) -> bool: ...

    def save_experiment(self, experiment: Experiment) -> None: ...

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

    def replace_experiment_exposure_for_date(
        self,
        experiment_id: str,
        date: str,
        exposure: ExperimentExposure | None,
    ) -> None: ...

    def list_daily_metrics(self) -> list[DailyMetric]: ...

    def list_daily_checkins(self) -> list[DailyCheckIn]: ...
