"""SQLite-backed experiment repository adapter.

This module is the persistence boundary for experiment definitions, exposure
rows, reports, and cached analysis snapshots. Application use cases depend on
the repository protocol; the SQLite and JsonStore details stay inside the
repository implementation below.
"""

from __future__ import annotations

from app.domains.experiments.contracts import (
    Experiment,
    ExperimentAnalysis,
    ExperimentExposure,
    ExperimentReport,
)
from app.domains.garmin_analytics.adapters import load_daily_metrics
from app.domains.garmin_health.contracts import DailyMetric
from app.domains.journal.contracts import DailyCheckIn
from app.infra.database import load_daily_checkins
from app.infra.jsonstore import JsonStore
from app.infra.sqlite import connect
from app.utils.timeutil import now_iso

_STORE = JsonStore({
    "experiments",
    "experiment_exposures",
    "experiment_reports",
})


class SqliteExperimentRepository:
    """Repository adapter used by experiment application use cases."""

    def list_experiments(
        self,
        *,
        statuses: tuple[str, ...] | None = None,
    ) -> list[Experiment]:
        where_sql = ""
        params: tuple[object, ...] = ()
        if statuses is not None:
            placeholders = ", ".join("?" for _ in statuses)
            where_sql = f"json_extract(data, '$.status') IN ({placeholders})"
            params = statuses
        return _STORE.load_many("experiments", Experiment, where_sql=where_sql, params=params)

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        return _STORE.load("experiments", Experiment, experiment_id)

    def experiment_exists(self, experiment_id: str) -> bool:
        return _STORE.exists("experiments", experiment_id)

    def save_experiment(self, experiment: Experiment) -> None:
        _STORE.save("experiments", experiment.id, experiment.model_dump_json())

    def delete_experiment(self, experiment_id: str) -> None:
        _STORE.delete("experiments", experiment_id)

    def list_all_experiment_analyses(self) -> dict[str, ExperimentAnalysis]:
        with connect() as con:
            rows = con.execute(
                "SELECT experiment_id, data FROM experiment_analyses"
            ).fetchall()
        return {
            row["experiment_id"]: ExperimentAnalysis.model_validate_json(row["data"])
            for row in rows
        }

    def get_experiment_analysis(self, experiment_id: str) -> ExperimentAnalysis | None:
        with connect() as con:
            row = con.execute(
                "SELECT data FROM experiment_analyses WHERE experiment_id = ?",
                (experiment_id,),
            ).fetchone()
        if row is None:
            return None
        return ExperimentAnalysis.model_validate_json(row["data"])

    def save_experiment_analysis(
        self,
        experiment_id: str,
        analysis: ExperimentAnalysis,
    ) -> None:
        now = now_iso()
        data_json = analysis.model_dump_json()
        with connect() as con, con:
            con.execute(
                "INSERT OR REPLACE INTO experiment_analyses "
                "(experiment_id, data, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (experiment_id, data_json, now, now),
            )

    def delete_experiment_analysis(self, experiment_id: str) -> None:
        with connect() as con, con:
            con.execute(
                "DELETE FROM experiment_analyses WHERE experiment_id = ?",
                (experiment_id,),
            )

    def list_experiment_exposures(
        self,
        *,
        experiment_id: str | None = None,
        date: str | None = None,
    ) -> list[ExperimentExposure]:
        clauses: list[str] = []
        params: list[object] = []
        if experiment_id is not None:
            clauses.append("experiment_id = ?")
            params.append(experiment_id)
        if date is not None:
            clauses.append("entry_date = ?")
            params.append(date)
        return _STORE.load_many(
            "experiment_exposures",
            ExperimentExposure,
            where_sql=" AND ".join(clauses),
            params=tuple(params),
            order_by="entry_date, created_at, id",
        )

    def save_experiment_exposure(self, exposure: ExperimentExposure) -> None:
        _STORE.save(
            "experiment_exposures",
            exposure.id,
            exposure.model_dump_json(),
            extra_columns={
                "experiment_id": exposure.experiment_id,
                "entry_date": exposure.date,
            },
        )

    def replace_experiment_exposure_for_date(
        self,
        experiment_id: str,
        date: str,
        exposure: ExperimentExposure | None,
    ) -> None:
        """Replace the derived exposure row for one experiment-day.

        Manual same-day exposure rows are preserved and take precedence over any
        derived exposure the sync service would otherwise write. The caller must
        pass either None or the canonical auto-id exposure for the target date.
        """
        auto_id = ExperimentExposure.auto_id(experiment_id, date)
        if exposure is not None and (
            exposure.experiment_id != experiment_id
            or exposure.date != date
            or exposure.id != auto_id
        ):
            raise ValueError("Exposure does not match experiment_id/date replacement target")

        with connect() as con, con:
            manual_exists = con.execute(
                """
                SELECT 1
                FROM experiment_exposures
                WHERE experiment_id = ? AND entry_date = ? AND id != ?
                LIMIT 1
                """,
                (experiment_id, date, auto_id),
            ).fetchone() is not None
            con.execute("DELETE FROM experiment_exposures WHERE id = ?", (auto_id,))
            if exposure is None or manual_exists:
                return
            _STORE.save_in_connection(
                con,
                "experiment_exposures",
                exposure.id,
                exposure.model_dump_json(),
                extra_columns={
                    "experiment_id": exposure.experiment_id,
                    "entry_date": exposure.date,
                },
            )

    def list_experiment_reports(
        self,
        experiment_id: str | None = None,
    ) -> list[ExperimentReport]:
        where_sql = "experiment_id = ?" if experiment_id is not None else ""
        params = (experiment_id,) if experiment_id is not None else ()
        return _STORE.load_many(
            "experiment_reports",
            ExperimentReport,
            where_sql=where_sql,
            params=params,
            order_by="report_date, created_at, id",
        )

    def save_experiment_report(self, report: ExperimentReport) -> None:
        _STORE.save(
            "experiment_reports",
            report.id,
            report.model_dump_json(),
            extra_columns={
                "experiment_id": report.experiment_id,
                "report_date": report.report_date,
            },
        )

    def list_daily_metrics(self) -> list[DailyMetric]:
        return load_daily_metrics()

    def list_daily_checkins(self) -> list[DailyCheckIn]:
        return load_daily_checkins()
