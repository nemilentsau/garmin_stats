"""Evidence + score-series assembly from daily metrics (R8).

Covers: seven evidence rows with the right source-type and tab link; the degraded flag
when the latest day has < 7 present inputs; the score series spanning the display window
with a seeded MA7; recovery-direction labelling; and the empty-input guard.
"""

from app.domains.garmin_analytics.domain.recovery_score.evidence import (
    METRIC_GETTERS,
    compute_recovery,
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


def _metric(
    date: str,
    *,
    resting: int | None = 50,
    hr_avg: float | None = 67.0,
    respiration: float | None = 13.0,
    body_battery: float | None = 31.0,
    hrv: float | None = 53.0,
    stress: float | None = 32.0,
    sleep: int | None = 66,
) -> DailyMetric:
    return DailyMetric(
        date=date,
        heart_rate=DailyHeartRateStats(avg=hr_avg, resting=resting),
        stress=DailyMetricStats(avg=stress),
        body_battery=DailyBodyBatteryStats(avg=body_battery),
        spo2=DailyMetricStats(),
        respiration=DailyMetricStats(avg=respiration),
        hrv=DailyHrvStats(nightly_avg=hrv),
        sleep=DailySleepStats(score=sleep),
        skin_temp=DailySkinTempStats(),
    )


def _baseline_series(days: int = 40) -> list[DailyMetric]:
    """A run of typical days so the 30-day warm-up clears before the latest day."""
    return [_metric(f"2025-06-{day:02d}") for day in range(1, days + 1)]


def _compute(metrics: list[DailyMetric]):
    result = compute_recovery(metrics)
    assert result is not None
    return result


def test_empty_metrics_returns_none():
    assert compute_recovery([]) is None


def test_warmup_dataset_returns_all_none_scores_without_crashing():
    # A non-empty series shorter than the 30-day warm-up: a fresh deployment hits
    # this. Every score is None, but the structure must still be populated.
    result = _compute(_baseline_series(20))
    assert len(result.score_series) == 20
    assert all(p.raw is None and p.ma7 is None for p in result.score_series)
    assert result.score_z is None and result.delta7_z is None and result.delta1_z is None
    assert [row.metric for row in result.evidence] == list(METRIC_GETTERS)
    # raw values are present; baseline and z are not yet computable
    hrv = next(r for r in result.evidence if r.metric == "hrv_nightly_avg")
    assert hrv.latest_value == 53.0 and hrv.baseline is None and hrv.delta_z is None
    # driver-series z is None across the whole warm-up window
    for series in result.driver_series:
        assert len(series.deltas_z) == 20 and all(z is None for z in series.deltas_z)


def test_produces_seven_evidence_rows_for_the_seven_axis_metrics():
    result = compute_recovery(_baseline_series())
    assert result is not None
    assert [row.metric for row in result.evidence] == list(METRIC_GETTERS)


def test_source_type_and_tab_links_are_assigned():
    rows = {row.metric: row for row in _compute(_baseline_series()).evidence}
    assert rows["respiration_avg"].source_type == "native"
    assert rows["heart_rate_resting"].source_type == "device"
    assert rows["hrv_nightly_avg"].source_type == "derived"
    assert rows["hrv_nightly_avg"].tab_href == "/hrv"
    assert rows["heart_rate_resting"].tab_href == "/heart-rate"
    assert rows["sleep_score"].tab_href == "/sleep"
    assert rows["body_battery_avg"].unit == ""


def test_recovery_direction_reflects_metric_sign():
    series = _baseline_series()
    # latest day: HRV well above baseline (good), resting HR well above baseline (bad)
    series.append(_metric("2025-07-11", hrv=85.0, resting=64))
    rows = {row.metric: row for row in _compute(series).evidence}
    assert rows["hrv_nightly_avg"].recovery_good is True
    assert rows["heart_rate_resting"].recovery_good is False


def test_degraded_flag_set_when_latest_day_has_few_inputs():
    series = _baseline_series()
    # latest day present on only 4 of 7 inputs -> composite undefined, degraded
    series.append(
        _metric(
            "2025-07-11",
            hr_avg=None,
            respiration=None,
            body_battery=None,
        )
    )
    result = _compute(series)
    assert all(row.degraded for row in result.evidence)


def test_score_series_spans_display_window_with_seeded_ma7():
    result = _compute(_baseline_series(45))
    # 45 days, 30-day warm-up -> 15 scored days, all within the display window
    assert len(result.score_series) == 45
    assert result.score_series[-1].ma7 is not None
    assert result.score_series[-1].baseline_lo == -0.5
    assert result.score_series[-1].baseline_hi == 0.5


def test_driver_series_aligns_with_score_window():
    result = _compute(_baseline_series(45))
    assert [s.metric for s in result.driver_series] == list(METRIC_GETTERS)
    n = len(result.score_series)
    for series in result.driver_series:
        assert (
            len(series.values)
            == len(series.baselines)
            == len(series.deltas_z)
            == len(series.recovery_good)
            == n
        )


def test_evidence_carries_baseline_and_sparkline():
    row = next(
        r for r in _compute(_baseline_series()).evidence
        if r.metric == "hrv_nightly_avg"
    )
    assert row.baseline == 53.0  # median of the typical history
    assert row.latest_value == 53.0
    assert len(row.sparkline) > 0 and row.sparkline[-1].value == 53.0


def test_score_points_carry_a_symmetric_dispersion_band():
    # Vary one input day to day so the rolling SD is > 0.
    metrics = []
    for i, day in enumerate(range(1, 41)):
        metrics.append(_metric(f"2025-06-{day:02d}", hr_avg=67.0 + (i % 5)))
    result = _compute(metrics)
    banded = [
        p for p in result.score_series
        if p.ma7 is not None and p.band_lo is not None and p.band_hi is not None
    ]
    assert banded, "expected at least one fully-banded score point"
    for p in banded:
        # band is ma7 +/- sd: symmetric around ma7, and non-degenerate here.
        assert p.ma7 is not None and p.band_lo is not None and p.band_hi is not None
        assert abs((p.band_hi - p.ma7) - (p.ma7 - p.band_lo)) < 1e-6
        assert p.band_hi >= p.ma7 >= p.band_lo


def test_band_is_none_when_ma7_is_none():
    # 40 days: display starts at day 31 (after the 30-day warm-up), so the first
    # displayed point has no prior seed to form a 7-day MA — ma7 is None there.
    result = _compute(_baseline_series(days=40))
    first = result.score_series[0]
    assert first.ma7 is None  # warm-up: no computable average yet
    assert first.band_lo is None
    assert first.band_hi is None
