"""Tests for reusable Garmin analytics calculation primitives."""

from dataclasses import dataclass
from importlib import import_module

import numpy as np

from app.domains.garmin_analytics.domain.primitives import trends
from app.domains.garmin_analytics.domain.primitives.trends import trailing_sd
from app.domains.garmin_health.domain.daily_metrics.hrv import classify_hrv_recovery
from app.utils import numeric


@dataclass(frozen=True)
class _MetricPoint:
    date: str
    value: float | None


def test_scalar_summary_computes_common_distribution_fields():
    assert hasattr(numeric, "summarize_scalar_values")

    summary = numeric.summarize_scalar_values([10, 20, 30, 40])

    assert summary.avg == 25.0
    assert summary.min == 10
    assert summary.max == 40
    assert summary.median == 25.0
    assert summary.q1 == 17.5
    assert summary.q3 == 32.5


def test_scalar_summary_rounds_extrema_only_when_requested():
    assert hasattr(numeric, "summarize_scalar_values")

    raw = numeric.summarize_scalar_values([12.24, 18.76])
    rounded = numeric.summarize_scalar_values([12.24, 18.76], rounded_extrema=True)

    assert raw.min == 12.24
    assert raw.max == 18.76
    assert rounded.min == 12.2
    assert rounded.max == 18.8


def test_scalar_summary_returns_null_fields_for_empty_values():
    assert hasattr(numeric, "summarize_scalar_values")

    summary = numeric.summarize_scalar_values([])

    assert summary.avg is None
    assert summary.min is None
    assert summary.max is None
    assert summary.median is None
    assert summary.q1 is None
    assert summary.q3 is None


def test_weekly_five_number_summary_groups_by_iso_week_and_skips_missing_values():
    assert hasattr(trends, "weekly_five_number_summaries")
    points = [
        _MetricPoint("2026-01-05", 10.0),
        _MetricPoint("2026-01-06", None),
        _MetricPoint("2026-01-07", 20.0),
        _MetricPoint("2026-01-12", 40.0),
        _MetricPoint("not-a-date", 100.0),
    ]

    summaries = trends.weekly_five_number_summaries(points, lambda point: point.value)

    assert [summary.iso_week for summary in summaries] == ["2026-W02", "2026-W03"]
    assert summaries[0].min == 10.0
    assert summaries[0].q1 == 12.5
    assert summaries[0].median == 15.0
    assert summaries[0].q3 == 17.5
    assert summaries[0].max == 20.0
    assert summaries[0].count == 2
    assert summaries[1].min == 40.0
    assert summaries[1].count == 1


def test_timestamp_coverage_summary_counts_records_and_ignores_unparseable_timestamps():
    timestamps = import_module(
        "app.domains.garmin_analytics.domain.primitives.timestamps"
    )
    assert hasattr(timestamps, "summarize_timestamp_coverage")

    summary = timestamps.summarize_timestamp_coverage([
        "2026-01-01T03:30:00",
        None,
        "not-a-timestamp",
        "2026-01-01T01:00:00",
    ])

    assert summary.sample_count == 4
    assert summary.coverage_start == "2026-01-01T01:00:00"
    assert summary.coverage_end == "2026-01-01T03:30:00"
    assert summary.coverage_hours == 2.5


def test_trailing_sd_returns_none_below_min_valid():
    # window has only 4 present values, min_valid=5 -> None
    out = trailing_sd([1.0, 2.0, 3.0, 4.0], window=14, min_valid=5)
    assert out == [None, None, None, None]


def test_trailing_sd_skips_none_inside_window():
    # present values are [2,4,6,8,10]; sample SD (ddof=1) of those
    out = trailing_sd([2.0, None, 4.0, 6.0, None, 8.0, 10.0], window=14, min_valid=5)
    expected = round(float(np.std([2.0, 4.0, 6.0, 8.0, 10.0], ddof=1)), 3)
    assert out[-1] == expected


def test_trailing_sd_constant_series_is_zero():
    out = trailing_sd([5.0] * 6, window=14, min_valid=5)
    assert out[-1] == 0.0


def test_trailing_sd_window_excludes_old_values():
    # window=3, min_valid=2: last position sees only the final 3 values
    out = trailing_sd([100.0, 1.0, 2.0, 3.0], window=3, min_valid=2)
    assert out[-1] == round(float(np.std([1.0, 2.0, 3.0], ddof=1)), 3)


def test_hrv_recovery_classifier_owns_shared_thresholds_and_status_policy():
    hrv_analysis = import_module("app.domains.garmin_analytics.domain.analysis.hrv")
    assert not hasattr(hrv_analysis, "classify_hrv_recovery")

    assert classify_hrv_recovery(delta=None) is None
    assert classify_hrv_recovery(delta=-10) == "suppressed"
    assert classify_hrv_recovery(delta=-9.9) == "below_baseline"  # no Garmin-status OR
    assert classify_hrv_recovery(delta=-5) == "below_baseline"
    assert classify_hrv_recovery(delta=8) == "elevated"
    assert classify_hrv_recovery(delta=0) == "stable"
    assert classify_hrv_recovery(delta=2.0) == "stable"  # positive delta is never "suppressed"


def test_nightly_trend_populates_trailing_band_after_warmup():
    from datetime import date, timedelta

    from app.domains.garmin_analytics.domain.analysis import hrv as hrv_analysis
    from app.domains.garmin_health.contracts import (
        DailyBodyBatteryStats,
        DailyHeartRateStats,
        DailyHrvStats,
        DailyMetric,
        DailyMetricStats,
        DailySkinTempStats,
        DailySleepStats,
    )

    def metric(d: str, nightly: float) -> DailyMetric:
        return DailyMetric(
            date=d,
            heart_rate=DailyHeartRateStats(avg=70.0, min=55, max=120, median=72.0, resting=48),
            stress=DailyMetricStats(avg=25.0),
            body_battery=DailyBodyBatteryStats(avg=60.0),
            spo2=DailyMetricStats(avg=96.0),
            respiration=DailyMetricStats(avg=14.0),
            hrv=DailyHrvStats(nightly_avg=nightly, weekly_avg=nightly, status="balanced"),
            sleep=DailySleepStats(score=85),
            skin_temp=DailySkinTempStats(deviation=0.1),
        )

    start = date(2026, 1, 1)
    metrics = [metric((start + timedelta(days=i)).isoformat(), 50.0 + (i % 5)) for i in range(25)]
    metrics.append(metric((start + timedelta(days=25)).isoformat(), 200.0))  # extreme night

    trend = hrv_analysis.compute_nightly_hrv_trend(metrics, window=30)

    assert trend[0].band_low is None  # warmup: fewer than 21 prior nights
    assert trend[22].band_low is not None and trend[22].band_high is not None
    assert trend[25].is_extreme is True
