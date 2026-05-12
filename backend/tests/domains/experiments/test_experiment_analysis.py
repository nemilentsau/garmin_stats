"""Integration tests for experiment analysis service."""

from datetime import date, timedelta
from typing import Any, cast

import pytest

import app.infra.database as db
from app.domains.experiments.adapters import SqliteExperimentRepository
from app.domains.experiments.application.analysis import compute_experiment_analysis
from app.domains.experiments.contracts import (
    AdherenceDayEntry,
    Experiment,
    ExperimentAnalysis,
    ExperimentDesign,
    ExperimentExposure,
    OutcomeMetric,
)
from app.domains.garmin_health.contracts import (
    DailyBodyBatteryStats,
    DailyHeartRateStats,
    DailyHrvStats,
    DailyMetric,
    DailyMetricStats,
    DailySkinTempStats,
    DailySleepStats,
)
from app.domains.journal.contracts import DailyCheckIn
from app.domains.routines.adapters import SqliteRoutineRepository


def _make_metric(
    d: str,
    hrv_nightly: float | None,
    sleep_score: int = 80,
    resting_hr: int = 55,
) -> DailyMetric:
    return DailyMetric(
        date=d,
        heart_rate=DailyHeartRateStats(resting=resting_hr),
        stress=DailyMetricStats(avg=30.0),
        body_battery=DailyBodyBatteryStats(),
        spo2=DailyMetricStats(),
        respiration=DailyMetricStats(),
        hrv=DailyHrvStats(
            nightly_avg=hrv_nightly,
            weekly_avg=hrv_nightly - 2 if hrv_nightly is not None else None,
        ),
        sleep=DailySleepStats(score=sleep_score),
        skin_temp=DailySkinTempStats(),
    )


def _store_metrics(metrics: list[DailyMetric]) -> None:
    """Insert synthetic daily metrics and invalidate the cached reads."""
    now_str = "2026-03-01T00:00:00+00:00"
    from app.infra import cache

    with db._connect() as con:
        for metric in metrics:
            con.execute(
                "INSERT OR REPLACE INTO daily_metrics (date, data, updated_at) VALUES (?, ?, ?)",
                (metric.date, metric.model_dump_json(), now_str),
            )
        con.commit()
    cache.invalidate()


def _seed_metrics(baseline_vals: list[float], treatment_vals: list[float]):
    """Insert synthetic daily metrics for a baseline + treatment window."""
    start = date(2026, 1, 1)
    metrics: list[DailyMetric] = []
    for i, val in enumerate(baseline_vals):
        d = (start + timedelta(days=i)).isoformat()
        metrics.append(_make_metric(d, val))

    treatment_start = start + timedelta(days=len(baseline_vals))
    for i, val in enumerate(treatment_vals):
        d = (treatment_start + timedelta(days=i)).isoformat()
        metrics.append(_make_metric(d, val))

    _store_metrics(metrics)


def _make_experiment(
    baseline_n: int,
    treatment_n: int,
    lag_days: list[int] | None = None,
) -> Experiment:
    start = date(2026, 1, 1)
    baseline_end = start + timedelta(days=baseline_n - 1)
    treatment_start = baseline_end + timedelta(days=1)
    treatment_end = treatment_start + timedelta(days=treatment_n - 1)

    return Experiment(
        id="test-experiment",
        name="Test → HRV",
        status="active",
        hypothesis="Testing improves HRV",
        design=ExperimentDesign(
            baseline_start_date=start.isoformat(),
            baseline_end_date=baseline_end.isoformat(),
            treatment_start_date=treatment_start.isoformat(),
            treatment_end_date=treatment_end.isoformat(),
            expected_lag_days=lag_days or [0],
            min_adherence_pct=0.70,
        ),
        outcome_metrics=[
            OutcomeMetric(path="hrv.nightly_avg", direction="higher_is_better"),
        ],
        confounder_watch=["sleep.score", "stress.avg"],
    )


class TestComputeExperimentAnalysis:
    def test_clear_improvement(self):
        """Treatment HRV clearly higher than baseline → large effect."""
        baseline = [40.0, 41.0, 42.0, 39.0, 40.0, 41.0, 42.0,
                    40.0, 41.0, 42.0, 39.0, 40.0, 41.0, 42.0]
        treatment = [50.0, 51.0, 52.0, 49.0, 50.0, 51.0, 52.0,
                     50.0, 51.0, 52.0, 49.0, 50.0, 51.0, 52.0]
        _seed_metrics(baseline, treatment)

        exp = _make_experiment(len(baseline), len(treatment))
        result = compute_experiment_analysis(SqliteExperimentRepository(), exp)

        assert result.experiment_id == "test-experiment"
        assert result.phase == "completed"
        assert result.days_in_baseline == 14
        assert result.days_in_treatment == 14
        assert len(result.metrics) == 1

        metric = result.metrics[0]
        assert metric.path == "hrv.nightly_avg"
        assert metric.best_result.direction_correct is True
        assert metric.best_result.delta_abs > 8
        assert metric.best_result.nap > 0.9
        assert metric.best_result.p_value_permutation < 0.05

    def test_no_effect(self):
        """Same data in both windows → no significant effect."""
        values = [40.0, 41.0, 42.0, 39.0, 40.0, 41.0, 42.0]
        _seed_metrics(values, values)

        exp = _make_experiment(len(values), len(values))
        result = compute_experiment_analysis(SqliteExperimentRepository(), exp)

        metric = result.metrics[0]
        assert abs(metric.best_result.delta_abs) < 1.0
        assert metric.best_result.nap == pytest.approx(0.5, abs=0.05)
        assert metric.best_result.p_value_permutation > 0.3

    def test_multi_lag_selects_best(self):
        """With lag offset, delayed treatment data should show stronger signal."""
        # Baseline: low
        baseline = [40.0] * 14
        # Treatment: first 5 days still low (lag), then high
        treatment = [40.0, 40.0, 40.0, 40.0, 40.0,
                     55.0, 55.0, 55.0, 55.0, 55.0, 55.0, 55.0, 55.0, 55.0]
        _seed_metrics(baseline, treatment)

        exp = _make_experiment(14, 14, lag_days=[0, 5])
        result = compute_experiment_analysis(SqliteExperimentRepository(), exp)

        metric = result.metrics[0]
        # The lag=5 result should be better than lag=0
        lag0 = next(r for r in metric.lag_results if r.lag_days == 0)
        lag5 = next(r for r in metric.lag_results if r.lag_days == 5)
        assert lag5.nap > lag0.nap
        assert metric.best_lag == 5

    def test_no_design_returns_draft(self):
        """Experiment without design gets a draft analysis."""
        exp = Experiment(id="no-design", name="No Design", status="draft")
        result = compute_experiment_analysis(SqliteExperimentRepository(), exp)
        assert result.phase == "draft"
        assert result.overall_confidence == "insufficient"

    def test_confounders_detected(self):
        """Check confounder analysis runs for numeric paths."""
        baseline = [40.0] * 14
        treatment = [50.0] * 14
        _seed_metrics(baseline, treatment)

        exp = _make_experiment(14, 14)
        result = compute_experiment_analysis(SqliteExperimentRepository(), exp)

        # We watch sleep.score and stress.avg — both should have checks
        assert len(result.confounders) == 2
        paths = {c.path for c in result.confounders}
        assert "sleep.score" in paths
        assert "stress.avg" in paths

    def test_confidence_insufficient_small_sample(self):
        """Very small samples → insufficient confidence."""
        baseline = [40.0, 41.0, 42.0]
        treatment = [50.0, 51.0, 52.0]
        _seed_metrics(baseline, treatment)

        exp = _make_experiment(3, 3)
        result = compute_experiment_analysis(SqliteExperimentRepository(), exp)
        assert result.overall_confidence == "insufficient"

    def test_lower_is_better_uses_direction_correct_nap(self):
        """Decreases in lower-is-better metrics should score as improvements."""
        start = date(2026, 1, 1)
        metrics: list[DailyMetric] = []
        for i in range(14):
            metrics.append(_make_metric(
                (start + timedelta(days=i)).isoformat(),
                hrv_nightly=45.0,
                resting_hr=72,
            ))
        for i in range(14):
            metrics.append(_make_metric(
                (start + timedelta(days=14 + i)).isoformat(),
                hrv_nightly=45.0,
                resting_hr=60,
            ))
        _store_metrics(metrics)

        exp = _make_experiment(14, 14)
        exp.outcome_metrics = [
            OutcomeMetric(path="heart_rate.resting", direction="lower_is_better"),
        ]
        exp.confounder_watch = []

        result = compute_experiment_analysis(SqliteExperimentRepository(), exp)

        metric = result.metrics[0]
        assert metric.best_result.direction_correct is True
        assert metric.best_result.nap > 0.9
        assert metric.best_result.nap_interpretation == "large"


class TestExperimentPreviewAndImport:
    def test_preview_validates_metric_path(self):
        """Preview should reject invalid metric paths."""
        from app.domains.experiments.application.preview import preview_experiment

        # Seed some data so baseline check passes
        _seed_metrics([40.0] * 14, [50.0] * 14)

        exp = Experiment(
            id="bad-path",
            name="Bad Path",
            status="draft",
            design=ExperimentDesign(
                baseline_start_date="2026-01-01",
                baseline_end_date="2026-01-14",
                treatment_start_date="2026-01-15",
                treatment_end_date="2026-01-28",
            ),
            outcome_metrics=[OutcomeMetric(path="nonexistent.metric")],
        )
        result = preview_experiment(
            SqliteExperimentRepository(), exp, routine_repo=SqliteRoutineRepository(),
        )
        assert not result.valid
        error_msgs = [i.message for i in result.issues if i.level == "error"]
        assert any("nonexistent.metric" in msg for msg in error_msgs)

    def test_preview_validates_dates(self):
        """Preview should catch invalid date ordering."""
        from app.domains.experiments.application.preview import preview_experiment

        exp = Experiment(
            id="bad-dates",
            name="Bad Dates",
            status="draft",
            design=ExperimentDesign(
                baseline_start_date="2026-01-15",
                baseline_end_date="2026-01-01",  # End before start
                treatment_start_date="2026-02-01",
            ),
            outcome_metrics=[OutcomeMetric(path="hrv.nightly_avg")],
        )
        result = preview_experiment(
            SqliteExperimentRepository(), exp, routine_repo=SqliteRoutineRepository(),
        )
        assert not result.valid

    def test_import_persists_and_analyses(self):
        """Import should create experiment and run analysis."""
        from app.domains.experiments.application.management import import_experiment

        _seed_metrics([40.0] * 14, [50.0] * 14)

        exp = Experiment(
            id="import-test",
            name="Import Test",
            status="draft",
            design=ExperimentDesign(
                baseline_start_date="2026-01-01",
                baseline_end_date="2026-01-14",
                treatment_start_date="2026-01-15",
                treatment_end_date="2026-01-28",
            ),
            outcome_metrics=[OutcomeMetric(path="hrv.nightly_avg")],
        )
        result = import_experiment(
            SqliteExperimentRepository(), exp, routine_repo=SqliteRoutineRepository(),
        )
        assert result.experiment.status == "active"
        assert result.analysis is not None
        assert result.analysis.days_in_baseline > 0

        # Verify persisted
        loaded = SqliteExperimentRepository().get_experiment("import-test")
        assert loaded is not None
        assert loaded.status == "active"

    def test_imported_analysis_with_flat_windows_round_trips_from_storage(self):
        """Persisted analyses should remain loadable for constant windows."""
        from app.domains.experiments.application.management import import_experiment

        _seed_metrics([40.0] * 14, [50.0] * 14)

        exp = Experiment(
            id="flat-series",
            name="Flat Series",
            status="draft",
            design=ExperimentDesign(
                baseline_start_date="2026-01-01",
                baseline_end_date="2026-01-14",
                treatment_start_date="2026-01-15",
                treatment_end_date="2026-01-28",
            ),
            outcome_metrics=[OutcomeMetric(path="hrv.nightly_avg")],
        )
        import_experiment(
            SqliteExperimentRepository(), exp, routine_repo=SqliteRoutineRepository(),
        )

        loaded = SqliteExperimentRepository().get_experiment_analysis("flat-series")

        assert loaded is not None
        result = loaded.metrics[0].best_result
        assert result.baseline_trend_p == 1.0
        assert result.autocorrelation_lag1_baseline == 0.0
        assert result.autocorrelation_lag1_treatment == 0.0

    def test_update_experiment_refreshes_saved_analysis(self):
        """Updating an experiment should refresh the persisted analysis payload."""
        from app.domains.experiments.application.management import (
            get_experiment_with_analysis,
            import_experiment,
            update_experiment,
        )

        _seed_metrics(
            [40.0, 41.0, 42.0, 39.0, 40.0, 41.0, 42.0, 40.0, 41.0, 42.0, 39.0, 40.0, 41.0, 42.0],
            [50.0, 51.0, 52.0, 49.0, 50.0, 51.0, 52.0, 50.0, 51.0, 52.0, 49.0, 50.0, 51.0, 52.0],
        )

        exp = Experiment(
            id="refresh-test",
            name="Refresh Test",
            status="draft",
            design=ExperimentDesign(
                baseline_start_date="2026-01-01",
                baseline_end_date="2026-01-14",
                treatment_start_date="2026-01-15",
                treatment_end_date="2026-01-28",
            ),
            outcome_metrics=[OutcomeMetric(path="hrv.nightly_avg")],
        )
        import_experiment(
            SqliteExperimentRepository(), exp, routine_repo=SqliteRoutineRepository(),
        )

        updated = Experiment(
            id="refresh-test",
            name="Refresh Test",
            status="active",
            design=exp.design,
            outcome_metrics=[OutcomeMetric(path="sleep.score")],
        )
        update_experiment(SqliteExperimentRepository(), "refresh-test", updated)

        detail = get_experiment_with_analysis(SqliteExperimentRepository(), "refresh-test")

        assert detail.analysis is not None
        assert detail.experiment.outcome_metrics[0].path == "sleep.score"
        assert detail.analysis.metrics[0].path == "sleep.score"

    def test_get_experiment_with_analysis_refreshes_stale_adherence_window(self, monkeypatch):
        """Reading yesterday's analysis should recompute adherence for today's date."""
        import app.domains.experiments.application.analysis as experiment_analysis_mod
        import app.domains.experiments.application.analysis_cache as analysis_cache_mod
        import app.domains.experiments.application.management as management_mod
        import app.domains.experiments.domain.analysis as experiment_domain_analysis_mod

        class Apr13(date):
            @classmethod
            def today(cls):
                return cls(2026, 4, 13)

        class May4(date):
            @classmethod
            def today(cls):
                return cls(2026, 5, 4)

        experiment = Experiment(
            id="stale-adherence",
            name="Meditation -> HRV",
            status="active",
            design=ExperimentDesign(
                baseline_start_date="2026-03-14",
                baseline_end_date="2026-04-10",
                treatment_start_date="2026-04-11",
                treatment_end_date="2026-04-24",
            ),
            outcome_metrics=[],
        )
        repo = SqliteExperimentRepository()
        repo.save_experiment(experiment)
        for day in ("2026-04-11", "2026-04-12", "2026-04-13"):
            repo.save_experiment_exposure(
                ExperimentExposure(
                    id=f"exposure:auto:{experiment.id}:{day}",
                    experiment_id=experiment.id,
                    date=day,
                    adherence_state="full",
                    exposure_score=1.0,
                )
            )

        monkeypatch.setattr(experiment_domain_analysis_mod, "date_type", Apr13)
        repo.save_experiment_analysis(
            experiment.id,
            experiment_analysis_mod.compute_experiment_analysis(repo, experiment),
        )
        stale = repo.get_experiment_analysis(experiment.id)
        assert stale is not None
        assert stale.adherence_rate == 1.0
        assert len(stale.adherence_by_day) == 3

        monkeypatch.setattr(experiment_domain_analysis_mod, "date_type", May4)

        analysis = analysis_cache_mod.get_experiment_analysis(repo, experiment.id)

        assert analysis is not None
        assert analysis.analysis_date == "2026-05-04"
        assert analysis.adherence_rate == 0.214
        assert len(analysis.adherence_by_day) == 14
        assert analysis.adherence_by_day[-1].date == "2026-04-24"
        assert analysis.adherence_by_day[-1].state == "unknown"

        repo.save_experiment_analysis(experiment.id, stale)
        detail = management_mod.get_experiment_with_analysis(repo, experiment.id)

        assert detail.analysis is not None
        assert detail.analysis.analysis_date == "2026-05-04"
        assert detail.analysis.adherence_rate == 0.214

    def test_get_experiment_analysis_refreshes_date_stale_snapshot_once(self, monkeypatch):
        """A date-stale active analysis should refresh once, then stay cached."""
        import app.domains.experiments.application.analysis as experiment_analysis_mod
        import app.domains.experiments.domain.analysis as experiment_domain_analysis_mod
        from app.domains.experiments.application import analysis_cache as analysis_cache_mod

        class Apr13(date):
            @classmethod
            def today(cls):
                return cls(2026, 4, 13)

        class May4(date):
            @classmethod
            def today(cls):
                return cls(2026, 5, 4)

        experiment = Experiment(
            id="date-only-stale",
            name="Date Only Stale",
            status="active",
            design=ExperimentDesign(
                baseline_start_date="2026-03-14",
                baseline_end_date="2026-04-10",
                treatment_start_date="2026-04-11",
                treatment_end_date="2026-04-12",
            ),
            outcome_metrics=[],
        )
        repo = SqliteExperimentRepository()
        repo.save_experiment(experiment)

        monkeypatch.setattr(experiment_domain_analysis_mod, "date_type", Apr13)
        repo.save_experiment_analysis(
            experiment.id,
            experiment_analysis_mod.compute_experiment_analysis(repo, experiment),
        )

        monkeypatch.setattr(experiment_domain_analysis_mod, "date_type", May4)
        write_calls: list[str] = []
        original_save = repo.save_experiment_analysis

        def tracking_save(experiment_id, analysis):
            write_calls.append(experiment_id)
            original_save(experiment_id, analysis)

        monkeypatch.setattr(repo, "save_experiment_analysis", tracking_save)

        analysis = analysis_cache_mod.get_experiment_analysis(repo, experiment.id)
        again = analysis_cache_mod.get_experiment_analysis(repo, experiment.id)
        persisted = repo.get_experiment_analysis(experiment.id)

        assert analysis is not None
        assert analysis.analysis_date == "2026-05-04"
        assert again is not None
        assert again.analysis_date == "2026-05-04"
        assert persisted is not None
        assert persisted.analysis_date == "2026-05-04"
        assert write_calls == [experiment.id]

    def test_refresh_active_experiment_analyses_skips_fresh_cached_snapshots(
        self,
        monkeypatch,
    ):
        """Scan refresh should not recompute active analyses that are already fresh."""
        import app.domains.experiments.domain.analysis as experiment_domain_analysis_mod
        from app.domains.experiments.application import analysis_cache as analysis_cache_mod

        class May4(date):
            @classmethod
            def today(cls):
                return cls(2026, 5, 4)

        monkeypatch.setattr(analysis_cache_mod, "date_type", May4)
        monkeypatch.setattr(experiment_domain_analysis_mod, "date_type", May4)

        experiment = Experiment(
            id="fresh-scan-cache",
            name="Fresh Scan Cache",
            status="active",
            design=ExperimentDesign(
                baseline_start_date="2026-03-14",
                baseline_end_date="2026-04-10",
                treatment_start_date="2026-04-11",
                treatment_end_date="2026-04-12",
            ),
            outcome_metrics=[],
        )
        cached = ExperimentAnalysis(
            experiment_id=experiment.id,
            analysis_date="2026-05-04",
            phase="completed",
            days_in_baseline=28,
            days_in_treatment=2,
            adherence_rate=0.0,
            adherence_by_day=[
                AdherenceDayEntry(date="2026-04-12", state="unknown"),
            ],
            metrics=[],
            confounders=[],
            overall_confidence="insufficient",
            summary="Cached analysis is current.",
        )

        class _FreshAnalysisRepo:
            def __init__(self):
                self.save_calls: list[str] = []

            def list_experiments(
                self,
                *,
                statuses: tuple[str, ...] | None = None,
            ) -> list[Experiment]:
                assert statuses == ("active",)
                return [experiment]

            def list_all_experiment_analyses(self) -> dict[str, ExperimentAnalysis]:
                return {experiment.id: cached}

            def list_daily_metrics(self) -> list[DailyMetric]:
                raise AssertionError("fresh active scan should not load metrics")

            def list_daily_checkins(self) -> list[DailyCheckIn]:
                raise AssertionError("fresh active scan should not load check-ins")

            def list_experiment_exposures(
                self,
                *,
                experiment_id: str | None = None,
                date: str | None = None,
            ) -> list[ExperimentExposure]:
                _ = (experiment_id, date)
                raise AssertionError("fresh active scan should not load exposures")

            def save_experiment_analysis(
                self,
                experiment_id: str,
                analysis: ExperimentAnalysis,
            ) -> None:
                _ = analysis
                self.save_calls.append(experiment_id)

        repo = _FreshAnalysisRepo()

        analyses = analysis_cache_mod.refresh_active_experiment_analyses(cast(Any, repo))

        assert analyses == {experiment.id: cached}
        assert repo.save_calls == []

    def test_manual_active_refresh_recomputes_fresh_cached_snapshots(
        self,
        monkeypatch,
    ):
        """Explicit refresh callers should recompute even when a cache looks fresh."""
        import app.domains.experiments.domain.analysis as experiment_domain_analysis_mod
        from app.domains.experiments.application import analysis_cache as analysis_cache_mod

        class May4(date):
            @classmethod
            def today(cls):
                return cls(2026, 5, 4)

        monkeypatch.setattr(analysis_cache_mod, "date_type", May4)
        monkeypatch.setattr(experiment_domain_analysis_mod, "date_type", May4)

        experiment = Experiment(
            id="forced-refresh",
            name="Forced Refresh",
            status="active",
            design=ExperimentDesign(
                baseline_start_date="2026-03-14",
                baseline_end_date="2026-04-10",
                treatment_start_date="2026-04-11",
                treatment_end_date="2026-04-12",
            ),
            outcome_metrics=[],
        )
        cached = ExperimentAnalysis(
            experiment_id=experiment.id,
            analysis_date="2026-05-04",
            phase="completed",
            days_in_baseline=28,
            days_in_treatment=2,
            adherence_rate=0.0,
            adherence_by_day=[
                AdherenceDayEntry(date="2026-04-12", state="unknown"),
            ],
            metrics=[],
            confounders=[],
            overall_confidence="insufficient",
            summary="Cached analysis is current.",
        )

        class _RefreshRepo:
            def __init__(self):
                self.input_loads: list[str] = []
                self.saved: list[ExperimentAnalysis] = []

            def list_experiments(
                self,
                *,
                statuses: tuple[str, ...] | None = None,
            ) -> list[Experiment]:
                assert statuses == ("active",)
                return [experiment]

            def list_all_experiment_analyses(self) -> dict[str, ExperimentAnalysis]:
                return {experiment.id: cached}

            def list_daily_metrics(self) -> list[DailyMetric]:
                self.input_loads.append("metrics")
                return []

            def list_daily_checkins(self) -> list[DailyCheckIn]:
                self.input_loads.append("checkins")
                return []

            def list_experiment_exposures(
                self,
                *,
                experiment_id: str | None = None,
                date: str | None = None,
            ) -> list[ExperimentExposure]:
                self.input_loads.append("exposures")
                assert experiment_id == experiment.id
                assert date is None
                return [
                    ExperimentExposure(
                        id="exposure-1",
                        experiment_id=experiment.id,
                        date="2026-04-11",
                        adherence_state="full",
                    ),
                    ExperimentExposure(
                        id="exposure-2",
                        experiment_id=experiment.id,
                        date="2026-04-12",
                        adherence_state="full",
                    ),
                ]

            def save_experiment_analysis(
                self,
                experiment_id: str,
                analysis: ExperimentAnalysis,
            ) -> None:
                assert experiment_id == experiment.id
                self.saved.append(analysis)

        repo = _RefreshRepo()

        refreshed = analysis_cache_mod.refresh_active_experiments(cast(Any, repo))

        assert refreshed == 1
        assert repo.input_loads == ["metrics", "checkins", "exposures"]
        assert len(repo.saved) == 1
        assert repo.saved[0].adherence_rate == 1.0
        assert repo.saved[0].summary != cached.summary

    def test_get_experiment_analysis_refreshes_completed_date_stale_snapshot(
        self,
        monkeypatch,
    ):
        """Completed experiments should still refresh stale cached analyses."""
        import app.domains.experiments.application.analysis as experiment_analysis_mod
        import app.domains.experiments.domain.analysis as experiment_domain_analysis_mod
        from app.domains.experiments.application import analysis_cache as analysis_cache_mod

        class Apr13(date):
            @classmethod
            def today(cls):
                return cls(2026, 4, 13)

        class May4(date):
            @classmethod
            def today(cls):
                return cls(2026, 5, 4)

        experiment = Experiment(
            id="completed-date-stale",
            name="Completed Date Stale",
            status="completed",
            design=ExperimentDesign(
                baseline_start_date="2026-03-14",
                baseline_end_date="2026-04-10",
                treatment_start_date="2026-04-11",
                treatment_end_date="2026-04-12",
            ),
            outcome_metrics=[],
        )
        repo = SqliteExperimentRepository()
        repo.save_experiment(experiment)

        monkeypatch.setattr(experiment_domain_analysis_mod, "date_type", Apr13)
        repo.save_experiment_analysis(
            experiment.id,
            experiment_analysis_mod.compute_experiment_analysis(repo, experiment),
        )

        monkeypatch.setattr(experiment_domain_analysis_mod, "date_type", May4)

        analysis = analysis_cache_mod.get_experiment_analysis(repo, experiment.id)
        persisted = repo.get_experiment_analysis(experiment.id)

        assert analysis is not None
        assert analysis.analysis_date == "2026-05-04"
        assert persisted is not None
        assert persisted.analysis_date == "2026-05-04"

    def test_crud_experiment_without_analysis_does_not_compute_on_read(self):
        """Simple CRUD experiments should remain readable without cached analysis."""
        from app.domains.experiments.application.management import (
            create_experiment,
            get_experiment_with_analysis,
            list_experiments,
        )

        experiment = Experiment(
            id="unvalidated-crud",
            name="Unvalidated CRUD",
            status="draft",
            design=ExperimentDesign(
                baseline_start_date="2026-01-01",
                baseline_end_date="2026-01-02",
                treatment_start_date="not-a-date",
            ),
        )
        create_experiment(SqliteExperimentRepository(), experiment)

        detail = get_experiment_with_analysis(SqliteExperimentRepository(), experiment.id)
        response = list_experiments(SqliteExperimentRepository())

        assert detail.experiment.id == experiment.id
        assert detail.analysis is None
        assert response.experiments[0].experiment.id == experiment.id
        assert response.experiments[0].analysis is None

    def test_preview_validates_metric_path_within_experiment_window(self):
        """Historical metrics inside the experiment window should still validate."""
        from app.domains.experiments.application.preview import preview_experiment

        start = date(2026, 1, 1)
        metrics: list[DailyMetric] = []
        for i in range(14):
            metrics.append(
                _make_metric((start + timedelta(days=i)).isoformat(), hrv_nightly=40.0 + i),
            )
        for i in range(14, 60):
            metrics.append(_make_metric((start + timedelta(days=i)).isoformat(), hrv_nightly=None))
        _store_metrics(metrics)

        exp = Experiment(
            id="window-validation",
            name="Window Validation",
            status="draft",
            design=ExperimentDesign(
                baseline_start_date="2026-01-01",
                baseline_end_date="2026-01-14",
                treatment_start_date="2026-01-15",
                treatment_end_date="2026-01-28",
            ),
            outcome_metrics=[OutcomeMetric(path="hrv.nightly_avg")],
        )

        result = preview_experiment(
            SqliteExperimentRepository(), exp, routine_repo=SqliteRoutineRepository(),
        )

        assert result.valid is True
