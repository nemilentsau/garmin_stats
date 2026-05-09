"""Tests for reusable Garmin analytics calculation primitives."""

from dataclasses import dataclass
from importlib import import_module

from app.domains.garmin_analytics.domain.analysis import hrv
from app.domains.garmin_analytics.domain.primitives import trends
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


def test_hrv_recovery_classifier_owns_shared_thresholds_and_status_policy():
    assert hasattr(hrv, "classify_hrv_recovery")

    assert hrv.classify_hrv_recovery(delta=None, status="Balanced") is None
    assert hrv.classify_hrv_recovery(delta=-10, status="Balanced") == "suppressed"
    assert hrv.classify_hrv_recovery(delta=-9.9, status="Low") == "suppressed"
    assert hrv.classify_hrv_recovery(delta=-5, status="Balanced") == "below_baseline"
    assert hrv.classify_hrv_recovery(delta=8, status="Balanced") == "elevated"
    assert hrv.classify_hrv_recovery(delta=0, status="Balanced") == "stable"
