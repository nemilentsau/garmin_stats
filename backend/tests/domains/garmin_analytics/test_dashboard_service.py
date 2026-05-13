"""Tests for dashboard overview service."""

import warnings

import pytest

import app.bootstrap.schema as storage_schema
import app.infra.sqlite as sqlite
from app.domains.garmin_analytics.adapters import (
    SqliteBiometricRepository,
)
from app.domains.garmin_analytics.application.dashboard import (
    get_dashboard_overview,
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
from app.infra import cache


def load_dashboard_overview():
    return get_dashboard_overview(SqliteBiometricRepository())


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(sqlite, "DB_PATH", test_db)
    cache.invalidate()
    storage_schema.init_storage()
    yield


def _make_metric(
    date: str,
    nightly_avg: float | None = 50.0,
    hrv_status: str | None = "balanced",
    sleep_score: int | None = 80,
    resting_hr: int | None = 46,
    weekly_avg: float | None = 50.0,
) -> DailyMetric:
    return DailyMetric(
        date=date,
        heart_rate=DailyHeartRateStats(
            avg=70.0, min=55, max=120, median=72.0, resting=resting_hr,
        ),
        stress=DailyMetricStats(avg=25.0),
        body_battery=DailyBodyBatteryStats(avg=60.0),
        spo2=DailyMetricStats(avg=96.0),
        respiration=DailyMetricStats(avg=14.0),
        hrv=DailyHrvStats(
            nightly_avg=nightly_avg, weekly_avg=weekly_avg,
            status=hrv_status,
        ),
        sleep=DailySleepStats(score=sleep_score),
        skin_temp=DailySkinTempStats(deviation=0.1),
    )


def _insert(metric: DailyMetric) -> None:
    with sqlite.connect() as con:
        con.execute(
            "INSERT INTO daily_metrics (date, data, updated_at) "
            "VALUES (?, ?, ?)",
            (metric.date, metric.model_dump_json(), "2026-01-15T00:00:00Z"),
        )
        con.commit()


class TestReadiness:
    def test_returns_none_when_sleep_and_status_both_missing(self):
        _insert(_make_metric(
            "2026-01-14", nightly_avg=50.0, hrv_status="balanced",
        ))
        _insert(_make_metric(
            "2026-01-15", sleep_score=None, hrv_status=None,
        ))

        result = load_dashboard_overview()
        assert result.readiness is None

    def test_computes_score_with_all_components_available(self):
        _insert(_make_metric(
            "2026-01-14", nightly_avg=60.0, resting_hr=46,
        ))
        _insert(_make_metric(
            "2026-01-15", nightly_avg=61.0, hrv_status="balanced",
            sleep_score=90, resting_hr=46,
        ))

        result = load_dashboard_overview()
        assert result.readiness is not None
        assert result.readiness.score is not None
        assert 0 <= result.readiness.score <= 100
        components = result.readiness.components
        assert "hrv_recovery" in components
        assert "sleep" in components
        assert "resting_hr" in components
        assert "hrv_status" in components
        total = sum(components.values())
        assert result.readiness.score == round(total)

    def test_label_ready_when_score_ge_75(self):
        # Elevated recovery + high sleep + good resting HR + balanced
        _insert(_make_metric(
            "2026-01-14", nightly_avg=50.0, resting_hr=50,
        ))
        _insert(_make_metric(
            "2026-01-15", nightly_avg=60.0, hrv_status="balanced",
            sleep_score=90, resting_hr=46,
        ))

        result = load_dashboard_overview()
        assert result.readiness is not None
        assert result.readiness.score is not None
        assert result.readiness.score >= 75
        assert result.readiness.label == "Ready"

    def test_label_moderate_when_score_50_to_74(self):
        _insert(_make_metric(
            "2026-01-14", nightly_avg=50.0, resting_hr=46,
        ))
        # delta=-6 + balanced → below_baseline(10), sleep 65→12.5,
        # resting delta=0→20, Balanced→25. Total=67.5→68
        _insert(_make_metric(
            "2026-01-15", nightly_avg=44.0, hrv_status="balanced",
            sleep_score=65, resting_hr=46,
        ))

        result = load_dashboard_overview()
        assert result.readiness is not None
        assert result.readiness.score is not None
        assert 50 <= result.readiness.score < 75
        assert result.readiness.label == "Moderate"

    def test_label_rest_when_score_lt_50(self):
        _insert(_make_metric(
            "2026-01-14", nightly_avg=60.0, resting_hr=46,
        ))
        _insert(_make_metric(
            "2026-01-15", nightly_avg=38.0, hrv_status="unbalanced",
            sleep_score=35, resting_hr=55,
        ))

        result = load_dashboard_overview()
        assert result.readiness is not None
        assert result.readiness.score is not None
        assert result.readiness.score < 50
        assert result.readiness.label == "Rest"

    def test_missing_resting_delta_uses_neutral_value(self):
        # Single day → no prior days for baseline → resting_delta is None
        _insert(_make_metric(
            "2026-01-15", nightly_avg=50.0, hrv_status="balanced",
            sleep_score=80, resting_hr=46,
        ))

        result = load_dashboard_overview()
        assert result.readiness is not None
        assert result.readiness.components["resting_hr"] == 12.0

    def test_status_driven_suppression_hint_does_not_claim_large_drop(self):
        _insert(_make_metric(
            "2026-01-14", nightly_avg=50.0, hrv_status="balanced", resting_hr=46,
        ))
        _insert(_make_metric(
            "2026-01-15", nightly_avg=70.0, hrv_status="unbalanced",
            sleep_score=80, resting_hr=46,
        ))

        result = load_dashboard_overview()
        assert result.readiness is not None
        assert result.readiness.components["hrv_recovery"] == 0.0
        assert result.readiness.component_hints["hrv_recovery"] == (
            "Garmin HRV status is unbalanced, which suppresses recovery "
            "without a 10+ ms drop vs your 7-day average"
        )

    def test_resting_hr_hint_keeps_sub_bpm_positive_delta(self):
        for i, resting_hr in enumerate([50, 50, 49, 49, 50], start=10):
            _insert(_make_metric(
                f"2026-01-{i:02d}",
                nightly_avg=50.0,
                hrv_status="balanced",
                sleep_score=80,
                resting_hr=resting_hr,
            ))
        _insert(_make_metric(
            "2026-01-15", nightly_avg=50.0, hrv_status="balanced",
            sleep_score=80, resting_hr=50,
        ))

        result = load_dashboard_overview()
        assert result.readiness is not None
        assert result.readiness.component_hints["resting_hr"] == (
            "Resting HR is 0.4 bpm above 7-day average — possible stress"
        )


class TestCorrelations:
    def _insert_days(
        self,
        count: int,
        sleep_score: int | None = 80,
        resting_hr: int | None = 46,
        nightly_avg: float | None = 50.0,
    ) -> None:
        for i in range(count):
            _insert(_make_metric(
                f"2026-01-{i + 1:02d}",
                nightly_avg=nightly_avg,
                sleep_score=sleep_score,
                resting_hr=resting_hr,
            ))

    def test_returns_empty_when_fewer_than_7_paired_points(self):
        self._insert_days(6)
        result = load_dashboard_overview()
        assert result.correlations == []

    def test_computes_pearson_r_for_sleep_score(self):
        for i in range(10):
            _insert(_make_metric(
                f"2026-01-{i + 1:02d}",
                nightly_avg=40.0 + i * 2.0,
                sleep_score=60 + i * 3,
            ))
        result = load_dashboard_overview()
        sleep_corr = next(
            (c for c in result.correlations if c.metric == "sleep_score"),
            None,
        )
        assert sleep_corr is not None
        assert sleep_corr.r_value is not None
        assert sleep_corr.sample_count == 10

    def test_computes_pearson_r_for_resting_hr(self):
        for i in range(10):
            _insert(_make_metric(
                f"2026-01-{i + 1:02d}",
                nightly_avg=40.0 + i * 2.0,
                resting_hr=50 - i,
            ))
        result = load_dashboard_overview()
        hr_corr = next(
            (c for c in result.correlations if c.metric == "resting_hr"),
            None,
        )
        assert hr_corr is not None
        assert hr_corr.r_value is not None
        assert hr_corr.r_value < 0  # inverse relationship

    def test_skips_days_with_none_nightly_avg(self):
        # 10 days but 5 have None nightly → only 5 pairs → below threshold
        for i in range(10):
            _insert(_make_metric(
                f"2026-01-{i + 1:02d}",
                nightly_avg=50.0 if i >= 5 else None,
                sleep_score=80,
            ))
        result = load_dashboard_overview()
        sleep_corr = next(
            (c for c in result.correlations if c.metric == "sleep_score"),
            None,
        )
        assert sleep_corr is None

    def test_skips_metric_when_all_other_values_none(self):
        for i in range(10):
            _insert(_make_metric(
                f"2026-01-{i + 1:02d}",
                nightly_avg=50.0,
                sleep_score=None,
                resting_hr=46,
            ))
        result = load_dashboard_overview()
        sleep_corr = next(
            (c for c in result.correlations if c.metric == "sleep_score"),
            None,
        )
        assert sleep_corr is None
        # resting_hr should still be present
        hr_corr = next(
            (c for c in result.correlations if c.metric == "resting_hr"),
            None,
        )
        assert hr_corr is not None

    def test_constant_series_returns_none_without_runtime_warning(self):
        for i in range(10):
            _insert(_make_metric(
                f"2026-01-{i + 1:02d}",
                nightly_avg=40.0 + i,
                sleep_score=80,
                resting_hr=46,
            ))

        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            result = load_dashboard_overview()

        sleep_corr = next(
            (c for c in result.correlations if c.metric == "sleep_score"),
            None,
        )
        hr_corr = next(
            (c for c in result.correlations if c.metric == "resting_hr"),
            None,
        )

        assert sleep_corr is not None
        assert sleep_corr.r_value is None
        assert hr_corr is not None
        assert hr_corr.r_value is None
