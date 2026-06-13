"""Tests for dashboard overview service."""

from datetime import date, timedelta

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
    spo2_avg: float | None = 96.0,
    skin_temp_deviation: float | None = 0.1,
) -> DailyMetric:
    return DailyMetric(
        date=date,
        heart_rate=DailyHeartRateStats(
            avg=70.0, min=55, max=120, median=72.0, resting=resting_hr,
        ),
        stress=DailyMetricStats(avg=25.0),
        body_battery=DailyBodyBatteryStats(avg=60.0),
        spo2=DailyMetricStats(avg=spo2_avg),
        respiration=DailyMetricStats(avg=14.0),
        hrv=DailyHrvStats(
            nightly_avg=nightly_avg, weekly_avg=weekly_avg,
            status=hrv_status,
        ),
        sleep=DailySleepStats(score=sleep_score),
        skin_temp=DailySkinTempStats(deviation=skin_temp_deviation),
    )


def _insert(metric: DailyMetric) -> None:
    with sqlite.connect() as con:
        con.execute(
            "INSERT INTO daily_metrics (date, data, updated_at) "
            "VALUES (?, ?, ?)",
            (metric.date, metric.model_dump_json(), "2026-01-15T00:00:00Z"),
        )
        con.commit()



def _seed_baseline(days: int = 40) -> None:
    """Insert `days` of varied typical metrics so the 30-day warm-up clears."""
    start = date(2026, 1, 1)
    for i in range(days):
        _insert(
            _make_metric(
                (start + timedelta(days=i)).isoformat(),
                nightly_avg=50.0 + (i % 7) - 3,   # ~47..53, real spread
                resting_hr=46 + (i % 5) - 2,      # ~44..48
                sleep_score=80 + (i % 6) - 3,     # ~77..82
            )
        )


_AXIS_METRICS = {
    "heart_rate_resting",
    "heart_rate_avg",
    "respiration_avg",
    "body_battery_avg",
    "hrv_nightly_avg",
    "stress_avg",
    "sleep_score",
}


class TestRecoveryOverview:
    def test_raises_when_no_metrics(self):
        with pytest.raises(LookupError):
            load_dashboard_overview()

    def test_seven_evidence_rows_cover_the_axis_metrics(self):
        _seed_baseline()
        result = load_dashboard_overview()
        assert {row.metric for row in result.evidence} == _AXIS_METRICS

    def test_evidence_rows_carry_source_type_and_tab_links(self):
        _seed_baseline()
        rows = {row.metric: row for row in load_dashboard_overview().evidence}
        assert rows["hrv_nightly_avg"].tab_href == "/hrv"
        assert rows["hrv_nightly_avg"].source_type == "derived"
        assert rows["heart_rate_resting"].tab_href == "/heart-rate"
        assert rows["respiration_avg"].source_type == "native"

    def test_two_health_flags_with_tab_links(self):
        _seed_baseline()
        flags = {flag.kind: flag for flag in load_dashboard_overview().flags}
        assert set(flags) == {"oxygen", "thermoregulation"}
        assert flags["oxygen"].tab_href == "/pulse-ox"
        assert flags["thermoregulation"].tab_href == "/skin-temp"

    def test_score_series_spans_window_with_seeded_ma7_and_band(self):
        _seed_baseline()
        result = load_dashboard_overview()
        assert len(result.score) > 0
        assert result.score[-1].ma7 is not None
        assert result.score[-1].baseline_lo == -0.5
        assert result.score[-1].baseline_hi == 0.5

    def test_state_has_a_band_when_the_latest_score_is_defined(self):
        _seed_baseline()
        state = load_dashboard_overview().state
        assert state.band in ("suppressed", "typical", "strong")
        assert state.score_z is not None

    def test_evidence_sorted_by_absolute_delta_z(self):
        _seed_baseline(39)
        _insert(_make_metric("2026-02-09", nightly_avg=20.0))  # big HRV drop
        result = load_dashboard_overview()
        deltas = [abs(row.delta_z) for row in result.evidence if row.delta_z is not None]
        assert deltas == sorted(deltas, reverse=True)
        assert result.evidence[0].metric == "hrv_nightly_avg"

    def test_full_response_is_well_formed_with_aligned_driver_series(self):
        _seed_baseline(50)
        result = load_dashboard_overview()
        assert result.change.delta7_z is not None  # 50 days clears warm-up + a Δ7 window
        assert {f.kind for f in result.flags} == {"oxygen", "thermoregulation"}
        assert len(result.driver_series) == 7
        # every driver series aligns index-for-index with the score window
        assert all(len(d.deltas_z) == len(result.score) for d in result.driver_series)
        assert isinstance(result.events, list) and isinstance(result.correlations, list)

    def test_warmup_dataset_yields_empty_state_not_a_crash(self):
        _seed_baseline(20)  # below the 30-day warm-up
        result = load_dashboard_overview()
        assert result.state.band is None and result.state.score_z is None
        assert len(result.evidence) == 7  # rows present (raw values), just no z yet

    def test_oxygen_flag_unknown_when_latest_spo2_missing(self):
        _seed_baseline(39)
        latest = _make_metric("2026-02-09").model_copy(
            update={"spo2": DailyMetricStats(avg=None)}
        )
        _insert(latest)
        oxygen = next(
            flag for flag in load_dashboard_overview().flags if flag.kind == "oxygen"
        )
        assert oxygen.state == "unknown"

    def test_historical_flag_series_preserves_past_oxygen_flags_when_latest_is_clear(self):
        _seed_baseline(40)
        _insert(_make_metric("2026-02-10", spo2_avg=84.0))
        _insert(_make_metric("2026-02-11", spo2_avg=96.0))

        result = load_dashboard_overview()

        latest_oxygen = next(flag for flag in result.flags if flag.kind == "oxygen")
        oxygen_series = next(
            series for series in result.flag_series if series.kind == "oxygen"
        )
        by_date = {point.date: point for point in oxygen_series.points}

        assert latest_oxygen.state == "clear"
        assert by_date["2026-02-10"].state == "flag"
        assert by_date["2026-02-11"].state == "clear"
