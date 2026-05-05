"""Tests for the target metric registry."""

import pytest

from app.domains.experiments.domain.target_metrics import (
    get_target_metric,
    list_target_metrics,
)


def test_lists_supported_target_metrics_in_stable_order():
    metrics = list_target_metrics()

    assert [metric.key for metric in metrics][:3] == [
        "body_battery_max",
        "body_battery_min",
        "deep_sleep_score",
    ]
    assert any(metric.key == "hrv_nightly" for metric in metrics)
    assert any(metric.path == "sleep.score" for metric in metrics)


def test_unknown_target_metric_raises_clear_error():
    with pytest.raises(KeyError, match="Unknown target metric"):
        get_target_metric("not_a_metric")
