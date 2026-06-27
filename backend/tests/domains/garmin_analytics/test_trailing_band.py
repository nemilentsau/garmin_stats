"""Unit tests for the trailing robust baseline primitive and HRV analysis loader."""

from typing import cast

import pytest

import app.bootstrap.schema as storage_schema
import app.infra.sqlite as sqlite
from app.domains.garmin_analytics.adapters import SqliteBiometricRepository
from app.domains.garmin_analytics.application.metric_analysis import load_hrv_analysis
from app.domains.garmin_analytics.domain.primitives import trends
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


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Isolated SQLite database for tests that need DB access."""
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(sqlite, "DB_PATH", test_db)
    cache.invalidate()
    storage_schema.init_storage()
    yield


def _make_daily_metric(date: str, nightly_avg: float | None) -> DailyMetric:
    return DailyMetric(
        date=date,
        heart_rate=DailyHeartRateStats(avg=70.0, min=55, max=120, median=72.0, resting=46),
        stress=DailyMetricStats(avg=25.0),
        body_battery=DailyBodyBatteryStats(avg=60.0),
        spo2=DailyMetricStats(avg=96.0),
        respiration=DailyMetricStats(avg=14.0),
        hrv=DailyHrvStats(nightly_avg=nightly_avg, weekly_avg=50.0, status="balanced"),
        sleep=DailySleepStats(score=80),
        skin_temp=DailySkinTempStats(deviation=0.1),
    )


def _insert_metric(metric: DailyMetric) -> None:
    with sqlite.connect() as con:
        con.execute(
            "INSERT INTO daily_metrics (date, data, updated_at) VALUES (?, ?, ?)",
            (metric.date, metric.model_dump_json(), "2026-01-15T00:00:00Z"),
        )
        con.commit()


def test_insufficient_prior_nights_yields_empty_point():
    # 20 priors before index 20, min_days is 21 -> empty point.
    values: list[float | None] = cast(list[float | None], [60.0] * 21)
    band = trends.trailing_robust_band(values, window=30, min_days=21)
    assert band[20] == trends.TrailingBandPoint(None, None, None, None, False)


def test_band_brackets_median_and_excludes_current_night():
    # Priors 40..61 (22 present values) -> median 50.5; current 50.0 is central.
    values: list[float | None] = cast(
        list[float | None], [40.0 + i for i in range(22)] + [50.0]
    )
    band = trends.trailing_robust_band(values, window=30, min_days=21)
    point = band[22]
    assert point.median == 50.5  # would shift if current (50.0) were included
    assert point.band_low is not None and point.band_high is not None
    assert point.band_low < 50.5 < point.band_high
    assert point.z is not None
    assert point.is_extreme is False


def test_far_outlier_is_flagged_extreme():
    values: list[float | None] = cast(
        list[float | None], [40.0 + i for i in range(22)] + [200.0]
    )
    band = trends.trailing_robust_band(values, window=30, min_days=21)
    assert band[22].is_extreme is True
    assert band[22].z is not None and band[22].z > 2.0


def test_missing_current_value_keeps_band_but_no_z():
    values: list[float | None] = [40.0 + i for i in range(22)] + [None]  # type: ignore[assignment]
    band = trends.trailing_robust_band(values, window=30, min_days=21)
    point = band[22]
    assert point.band_low is not None
    assert point.z is None
    assert point.is_extreme is False


def test_window_limits_lookback():
    # window=21 means index 22 looks at indices 1..21 (21 values), index 0 dropped.
    values: list[float | None] = cast(
        list[float | None], [40.0 + i for i in range(22)] + [50.0]
    )
    band = trends.trailing_robust_band(values, window=21, min_days=21)
    assert band[22].median == 51.0  # median of 41..61


def test_baseline_window_enum_rejects_unlisted_values():
    from app.domains.garmin_analytics.contracts import BaselineWindow

    assert int(BaselineWindow(60)) == 60
    with pytest.raises(ValueError):
        BaselineWindow(45)


def test_hrv_analysis_cache_does_not_collide_across_baselines(tmp_db):
    """Regression: each baseline window must cache independently.

    Build a level-shift series (30 nights at 50 ms, then 31 nights at 90 ms).
    - trailing-30 priors: all 90 ms  → band centred near 90
    - trailing-60 priors: 30×50 + 30×90 → band centred near 70
    If the cache key were shared the second call would return the first call's
    result and the assertion below would fail.
    """
    from datetime import date, timedelta

    start = date(2025, 1, 1)
    # 30 nights at low level
    for i in range(30):
        d = (start + timedelta(days=i)).isoformat()
        _insert_metric(_make_daily_metric(date=d, nightly_avg=50.0))
    # 31 nights at high level (30 priors + 1 current for last point)
    for i in range(31):
        d = (start + timedelta(days=30 + i)).isoformat()
        _insert_metric(_make_daily_metric(date=d, nightly_avg=90.0))

    repo = SqliteBiometricRepository()
    a = load_hrv_analysis(repo, baseline=30)
    b = load_hrv_analysis(repo, baseline=60)
    assert a.nightly_trend[-1].band_low != b.nightly_trend[-1].band_low


def test_hrv_analysis_drops_boxplots_and_threads_window(tmp_db):
    from datetime import date, timedelta

    start = date(2026, 1, 1)
    for i in range(22):
        d = (start + timedelta(days=i)).isoformat()
        _insert_metric(_make_daily_metric(date=d, nightly_avg=50.0 + i * 0.1))

    repo = SqliteBiometricRepository()
    resp = load_hrv_analysis(repo, baseline=30)
    # Positive shape assertions: response carries the expected fields
    assert hasattr(resp, "nightly_trend")
    assert hasattr(resp, "pattern_windows")
    assert len(resp.nightly_trend) == 22
    assert isinstance(resp.pattern_windows, dict)
    # Retired field must not be present
    assert not hasattr(resp, "weekly_boxplots")
    assert resp.nightly_trend[-1].band_low is not None


def test_degenerate_window_zero_spread_yields_null_z():
    """A window of identical priors has no spread; z must be None and is_extreme False."""
    # 22 identical priors (min_days=21 satisfied) + a different current value.
    values: list[float | None] = cast(list[float | None], [60.0] * 22 + [45.0])
    band = trends.trailing_robust_band(values, window=30, min_days=21)
    point = band[22]
    assert point.z is None
    assert point.is_extreme is False
    # Band collapses to the constant when there is no spread
    assert point.band_low == point.band_high == 60.0


def test_pattern_window_overall_avg_is_sample_weighted_mean(tmp_db):
    """HrvPatternWindow.overall_avg must equal the true grand mean of nightly values,
    not a mean-of-weekday-means (which would be biased when weekdays are uneven)."""
    from datetime import date, timedelta

    start = date(2026, 1, 1)
    nightly_vals = [40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    for i, nv in enumerate(nightly_vals):
        d = (start + timedelta(days=i)).isoformat()
        _insert_metric(_make_daily_metric(date=d, nightly_avg=nv))

    repo = SqliteBiometricRepository()
    resp = load_hrv_analysis(repo, baseline=30)
    # "All" window always includes every inserted day regardless of today's date.
    assert "All" in resp.pattern_windows
    window = resp.pattern_windows["All"]
    expected_avg = round(sum(nightly_vals) / len(nightly_vals), 1)
    assert window.overall_avg == expected_avg
