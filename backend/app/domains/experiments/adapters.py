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
)
from app.infra.jsonstore import JsonStore
from app.infra.sqlite import connect
from app.utils.timeutil import now_iso

_STORE = JsonStore({
    "experiments",
    "experiment_exposures",
})


class SqliteExperimentRepository:
    """Repository adapter used by experiment application use cases."""

    def list_experiments(
        self,
        *,
        statuses: tuple[str, ...] | None = None,
    ) -> list[Experiment]:
        """Load experiment definitions, optionally filtered by lifecycle status."""
        where_sql = ""
        params: tuple[object, ...] = ()
        if statuses is not None:
            where_sql, params = _STORE.status_predicate(statuses)
        return _STORE.load_many("experiments", Experiment, where_sql=where_sql, params=params)

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        """Load one experiment definition by id."""
        return _STORE.load("experiments", Experiment, experiment_id)

    def experiment_exists(self, experiment_id: str) -> bool:
        """Return whether an experiment definition exists without loading it."""
        return _STORE.exists("experiments", experiment_id)

    def save_experiment(self, experiment: Experiment) -> None:
        """Persist one experiment definition."""
        _STORE.save("experiments", experiment.id, experiment.model_dump_json())

    def list_all_experiment_analyses(self) -> dict[str, ExperimentAnalysis]:
        """Load all cached analysis snapshots keyed by experiment id."""
        with connect() as con:
            rows = con.execute(
                "SELECT experiment_id, data FROM experiment_analyses"
            ).fetchall()
        return {
            row["experiment_id"]: ExperimentAnalysis.model_validate_json(row["data"])
            for row in rows
        }

    def get_experiment_analysis(self, experiment_id: str) -> ExperimentAnalysis | None:
        """Load the cached analysis snapshot for one experiment."""
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
        """Upsert the cached analysis snapshot keyed by experiment id."""
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
        """Delete any cached analysis snapshot for an experiment."""
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
        """Load exposure rows filtered by experiment id, date, or both."""
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
        """Upsert the single manual exposure for one experiment-day."""
        _STORE.save(
            "experiment_exposures",
            exposure.id,
            exposure.model_dump_json(),
            extra_columns={
                "experiment_id": exposure.experiment_id,
                "entry_date": exposure.date,
            },
        )
