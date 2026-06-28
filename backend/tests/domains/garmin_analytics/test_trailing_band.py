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


def test_is_extreme_uses_the_displayed_rounded_z_just_above_threshold():
    """A raw z in [2.000, 2.005) rounds to a displayed 2.00, which is NOT > 2.0, so the
    night must not be flagged extreme — the flag and the shown number must agree."""
    from app.utils.numeric import robust_center_scale

    priors = [40.0] * 7 + [50.0] * 7 + [60.0] * 7  # 21 priors, non-zero spread
    median, scale = robust_center_scale(priors)
    # Place the current night so the raw z sits just above the threshold but rounds down.
    current = median + 2.002 * scale
    values = cast(list[float | None], priors + [current])
    point = trends.trailing_robust_band(values, window=30, min_days=21)[21]
    assert point.z == 2.0  # displayed value rounds to exactly the threshold
    assert point.is_extreme is False  # 2.00 is not > 2.0 -> not extreme


def test_is_extreme_when_rounded_z_clears_threshold():
    """The companion boundary: a raw z that rounds to 2.01 does exceed 2.0 and is flagged."""
    from app.utils.numeric import robust_center_scale

    priors = [40.0] * 7 + [50.0] * 7 + [60.0] * 7
    median, scale = robust_center_scale(priors)
    current = median + 2.010 * scale
    values = cast(list[float | None], priors + [current])
    point = trends.trailing_robust_band(values, window=30, min_days=21)[21]
    assert point.z is not None and point.z > 2.0
    assert point.is_extreme is True


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
    assert all(not hasattr(window, "distribution") for window in resp.pattern_windows.values())
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


def test_single_point_matches_full_band_at_index():
    """trailing_band_point(values, i) must equal trailing_robust_band(values)[i] for every i,
    so the single-index fast path used by selected-day insights preserves the numbers across
    the empty (i < min_days), boundary, and computed cases."""
    values: list[float | None] = cast(
        list[float | None], [40.0 + (i % 7) for i in range(40)]
    )
    full = trends.trailing_robust_band(values, window=30, min_days=21)
    for i in (0, 20, 21, 25, 39):
        assert (
            trends.trailing_band_point(values, i, window=30, min_days=21) == full[i]
        )


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


def test_pattern_window_total_sample_count_is_backend_owned(tmp_db):
    """total_sample_count must equal the sum of the weekday buckets and count only
    present nightly values, so the frontend can render it without any aggregation."""
    from datetime import date, timedelta

    start = date(2026, 1, 1)
    present = 10
    for i in range(present):
        d = (start + timedelta(days=i)).isoformat()
        _insert_metric(_make_daily_metric(date=d, nightly_avg=50.0 + i))
    # Two nights with no nightly HRV must not be counted.
    for i in range(present, present + 2):
        d = (start + timedelta(days=i)).isoformat()
        _insert_metric(_make_daily_metric(date=d, nightly_avg=None))

    repo = SqliteBiometricRepository()
    window = load_hrv_analysis(repo, baseline=30).pattern_windows["All"]
    assert window.total_sample_count == present
    assert window.total_sample_count == sum(b.sample_count for b in window.day_of_week)


def test_nightly_trend_breaks_at_gaps(tmp_db):
    """The trend must densify to a full daily calendar and emit all-null gap points for any
    night without an HRV reading — both entirely-absent days (no row) and present rows with a
    null reading — so the chart breaks instead of bridging."""
    from datetime import date, timedelta

    start = date(2026, 2, 1)
    # Insert Feb 1..10 but SKIP Feb 5 entirely (absent day) and give Feb 8 a null reading.
    for i in range(10):
        d = start + timedelta(days=i)
        if d == date(2026, 2, 5):
            continue  # entirely absent — no row at all
        nightly = None if d == date(2026, 2, 8) else 50.0 + i
        _insert_metric(_make_daily_metric(date=d.isoformat(), nightly_avg=nightly))

    repo = SqliteBiometricRepository()
    trend = load_hrv_analysis(repo, baseline=30).nightly_trend
    by_date = {p.date: p for p in trend}

    # Densified to the full inclusive calendar span (Feb 1..10 = 10 points), contiguous.
    assert len(trend) == 10
    assert [p.date for p in trend] == [
        (start + timedelta(days=i)).isoformat() for i in range(10)
    ]

    # Both gap kinds are all-null break points.
    for gap in ("2026-02-05", "2026-02-08"):
        assert by_date[gap].nightly_avg is None
        assert by_date[gap].ma7 is None
        assert by_date[gap].band_low is None and by_date[gap].band_high is None
        assert by_date[gap].z is None and by_date[gap].is_extreme is False

    # A real night still carries its reading and MA (band is null here — too few priors).
    assert by_date["2026-02-10"].nightly_avg is not None
    assert by_date["2026-02-10"].ma7 is not None


def test_nightly_trend_band_matches_selected_day_panel(tmp_db):
    """Densifying the trend must not break the guarantee that the chart band and the panel
    agree for a given night + window: a real night's trend z/is_extreme equals the
    selected-day panel's."""
    from datetime import date, timedelta

    from app.domains.garmin_analytics.application.metric_insights import get_hrv_insights

    start = date(2026, 3, 1)
    for i in range(30):
        d = (start + timedelta(days=i)).isoformat()
        _insert_metric(_make_daily_metric(date=d, nightly_avg=50.0 + (i % 6)))

    repo = SqliteBiometricRepository()
    target = (start + timedelta(days=28)).isoformat()  # 28 priors >= min_days
    trend_point = {p.date: p for p in load_hrv_analysis(repo, baseline=30).nightly_trend}[target]
    panel = get_hrv_insights(repo, target, baseline=30).baseline

    assert panel is not None
    assert trend_point.z == panel.selected_z
    assert trend_point.is_extreme == panel.selected_is_extreme


def test_pattern_windows_are_identical_across_baseline_windows(tmp_db):
    """Weekday pattern windows do not depend on the baseline knob, so /analysis returns the
    same pattern data for every baseline (it is computed and cached once, not per window)."""
    from datetime import date, timedelta

    start = date(2026, 1, 1)
    for i in range(40):
        d = (start + timedelta(days=i)).isoformat()
        _insert_metric(_make_daily_metric(date=d, nightly_avg=50.0 + (i % 5)))

    repo = SqliteBiometricRepository()
    a30 = load_hrv_analysis(repo, baseline=30)
    a90 = load_hrv_analysis(repo, baseline=90)
    assert a30.pattern_windows == a90.pattern_windows
    # The per-window nightly trend still differs (band depends on the window); the
    # collision regression is covered by test_hrv_analysis_cache_does_not_collide_across_baselines.


def test_nightly_trend_state_classifies_ma_against_band(tmp_db):
    """trend_state colors the historical strip by the averaged trend: it classifies the
    7-day MA against the trailing typical-range band (below / within / above), and is None
    for warmup/gap points."""
    from datetime import date, timedelta

    start = date(2026, 4, 1)
    # 30 nights so later points have a real band; mostly ~60 ms, then a sustained drop.
    for i in range(25):
        d = (start + timedelta(days=i)).isoformat()
        _insert_metric(_make_daily_metric(date=d, nightly_avg=60.0 + (i % 4)))
    for i in range(25, 35):
        d = (start + timedelta(days=i)).isoformat()
        _insert_metric(_make_daily_metric(date=d, nightly_avg=35.0))  # sustained low

    repo = SqliteBiometricRepository()
    trend = {p.date: p for p in load_hrv_analysis(repo, baseline=30).nightly_trend}

    # Warmup: first point has no band -> no trend_state.
    assert trend[start.isoformat()].trend_state is None
    # After a sustained drop, the MA sits below the trailing band.
    assert trend[(start + timedelta(days=34)).isoformat()].trend_state == "below"
    # Every classified value is one of the allowed states.
    assert {p.trend_state for p in trend.values()} <= {None, "below", "within", "above"}


def test_no_reading_night_keeps_trend_state_but_breaks_chart(tmp_db):
    """A no-reading night past warmup carries a trend_state so the history strip stays a
    continuous trend heatmap (no gray hole), while its chart fields stay null so the MA line
    and ribbon still break at the missing night."""
    from datetime import date, timedelta

    start = date(2026, 5, 1)
    for i in range(25):  # 25 readings -> past the 21-night band floor
        d = (start + timedelta(days=i)).isoformat()
        _insert_metric(_make_daily_metric(date=d, nightly_avg=55.0 + (i % 4)))
    gap = (start + timedelta(days=25)).isoformat()
    _insert_metric(_make_daily_metric(date=gap, nightly_avg=None))  # row present, no HRV reading

    repo = SqliteBiometricRepository()
    pt = {p.date: p for p in load_hrv_analysis(repo, baseline=30).nightly_trend}[gap]
    # Chart fields stay null -> the line and ribbon break at the missing night.
    assert pt.nightly_avg is None and pt.ma7 is None
    assert pt.band_low is None and pt.band_high is None
    # ...but the strip still has a trend classification for it (not a gray hole).
    assert pt.trend_state in {"below", "within", "above"}


def test_hrv_pattern_cache_refreshes_after_invalidation(tmp_db):
    """The shared pattern cache must participate in generation invalidation: a re-ingest
    (cache.invalidate) refreshes it instead of serving the pre-ingest patterns."""
    from datetime import date, timedelta

    start = date(2026, 1, 1)
    for i in range(25):
        d = (start + timedelta(days=i)).isoformat()
        _insert_metric(_make_daily_metric(date=d, nightly_avg=50.0))

    repo = SqliteBiometricRepository()
    first_total = load_hrv_analysis(repo, baseline=30).pattern_windows["All"].total_sample_count

    # Simulate a re-ingest: more nights land, then the cache generation is bumped.
    for i in range(25, 30):
        d = (start + timedelta(days=i)).isoformat()
        _insert_metric(_make_daily_metric(date=d, nightly_avg=50.0))
    cache.invalidate()

    second_total = load_hrv_analysis(repo, baseline=30).pattern_windows["All"].total_sample_count
    assert second_total == first_total + 5
