"""SQLite repository adapter for experiment use cases."""

from __future__ import annotations

from app.domains.experiments.contracts import (
    Experiment,
    ExperimentAnalysis,
    ExperimentExposure,
)
from app.domains.garmin_analytics.adapters import load_daily_metrics
from app.domains.garmin_health.contracts import DailyMetric
from app.domains.journal.contracts import DailyCheckIn
from app.infra.database import (
    delete_experiment_analysis,
    experiment_exists,
    load_all_experiment_analyses,
    load_daily_checkins,
    load_experiment,
    load_experiment_analysis,
    load_experiment_exposures,
    load_experiments,
    replace_experiment_exposure_for_date,
    save_experiment,
    save_experiment_analysis,
    save_experiment_exposure,
)


class SqliteExperimentRepository:
    def list_experiments(
        self,
        *,
        statuses: tuple[str, ...] | None = None,
    ) -> list[Experiment]:
        return load_experiments(statuses=statuses)

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        return load_experiment(experiment_id)

    def experiment_exists(self, experiment_id: str) -> bool:
        return experiment_exists(experiment_id)

    def save_experiment(self, experiment: Experiment) -> None:
        save_experiment(experiment)

    def list_all_experiment_analyses(self) -> dict[str, ExperimentAnalysis]:
        return load_all_experiment_analyses()

    def get_experiment_analysis(self, experiment_id: str) -> ExperimentAnalysis | None:
        return load_experiment_analysis(experiment_id)

    def save_experiment_analysis(
        self,
        experiment_id: str,
        analysis: ExperimentAnalysis,
    ) -> None:
        save_experiment_analysis(experiment_id, analysis)

    def delete_experiment_analysis(self, experiment_id: str) -> None:
        delete_experiment_analysis(experiment_id)

    def list_experiment_exposures(
        self,
        *,
        experiment_id: str | None = None,
        date: str | None = None,
    ) -> list[ExperimentExposure]:
        return load_experiment_exposures(experiment_id=experiment_id, date=date)

    def save_experiment_exposure(self, exposure: ExperimentExposure) -> None:
        save_experiment_exposure(exposure)

    def replace_experiment_exposure_for_date(
        self,
        experiment_id: str,
        date: str,
        exposure: ExperimentExposure | None,
    ) -> None:
        replace_experiment_exposure_for_date(experiment_id, date, exposure)

    def list_daily_metrics(self) -> list[DailyMetric]:
        return load_daily_metrics()

    def list_daily_checkins(self) -> list[DailyCheckIn]:
        return load_daily_checkins()
