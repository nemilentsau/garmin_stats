"""Backend-owned registry for experiment target metrics."""

from app.models import TargetMetricDefinition

_TARGET_METRICS = {
    "resting_hr": TargetMetricDefinition(
        key="resting_hr",
        label="Resting HR",
        path="heart_rate.resting",
        unit="bpm",
    ),
    "hrv_nightly": TargetMetricDefinition(
        key="hrv_nightly",
        label="Nightly HRV",
        path="hrv.nightly_avg",
        unit="ms",
    ),
    "hrv_weekly": TargetMetricDefinition(
        key="hrv_weekly",
        label="Weekly HRV",
        path="hrv.weekly_avg",
        unit="ms",
    ),
    "sleep_score": TargetMetricDefinition(
        key="sleep_score",
        label="Sleep Score",
        path="sleep.score",
        unit="pts",
    ),
    "deep_sleep_score": TargetMetricDefinition(
        key="deep_sleep_score",
        label="Deep Sleep Score",
        path="sleep.deep_score",
        unit="pts",
    ),
    "stress_avg": TargetMetricDefinition(
        key="stress_avg",
        label="Average Stress",
        path="stress.avg",
        unit="0-100",
    ),
    "body_battery_min": TargetMetricDefinition(
        key="body_battery_min",
        label="Body Battery Min",
        path="body_battery.min",
        unit="0-100",
    ),
    "body_battery_max": TargetMetricDefinition(
        key="body_battery_max",
        label="Body Battery Max",
        path="body_battery.max",
        unit="0-100",
    ),
    "spo2_avg": TargetMetricDefinition(
        key="spo2_avg",
        label="SpO2 Avg",
        path="spo2.avg",
        unit="%",
    ),
    "skin_temp_deviation": TargetMetricDefinition(
        key="skin_temp_deviation",
        label="Skin Temp Deviation",
        path="skin_temp.deviation",
        unit="C",
    ),
}


def list_target_metrics() -> list[TargetMetricDefinition]:
    """Return the supported target metrics in stable key order."""
    return [_TARGET_METRICS[key] for key in sorted(_TARGET_METRICS)]


def get_target_metric(key: str) -> TargetMetricDefinition:
    """Return a target metric definition or raise KeyError if unknown."""
    try:
        return _TARGET_METRICS[key]
    except KeyError as exc:
        raise KeyError(f"Unknown target metric: {key}") from exc
