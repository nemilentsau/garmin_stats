"""Tests for the target metric registry."""

from app.domains.experiments.application.target_metrics import list_target_metrics


def test_lists_supported_target_metrics_in_stable_order():
    metrics = list_target_metrics()

    assert [metric.key for metric in metrics][:3] == [
        "body_battery_max",
        "body_battery_min",
        "deep_sleep_score",
    ]
    assert any(metric.key == "hrv_nightly" for metric in metrics)
    assert any(metric.path == "sleep.score" for metric in metrics)
