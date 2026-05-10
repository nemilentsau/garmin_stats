"""Confounder checks for experiment analysis."""

from __future__ import annotations

import numpy as np

from app.domains.experiments.contracts import ConfounderCheck
from app.domains.garmin_health.contracts import DailyMetric
from app.domains.journal.contracts import DailyCheckIn

from .metric_paths import resolve_path
from .statistics import welch_t_test
from .windows import date_range

_P_MODERATE = 0.10
_CONFOUNDER_FLAG_THRESHOLD = 0.15
_CONFOUNDER_NUMERIC_THRESHOLD = 10


def _extract_confounder(
    metrics_map: dict[str, DailyMetric],
    checkins_map: dict[str, DailyCheckIn],
    path: str,
    start: str,
    end: str,
) -> list[float] | tuple[int, int]:
    """Extract boolean checkin flags as counts and numeric paths as samples."""
    is_checkin_bool = path.startswith("checkin.") and path.split(".")[-1].endswith("_flag")
    days = date_range(start, end)

    if is_checkin_bool:
        field = path.removeprefix("checkin.")
        flag_count = sum(
            1 for day in days
            if getattr(checkins_map.get(day), field, False)
        )
        return flag_count, len(days)

    values: list[float] = []
    for day in days:
        value = resolve_path(metrics_map.get(day), checkins_map.get(day), path)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    return values


def check_confounders(
    confounder_paths: list[str],
    metrics_map: dict[str, DailyMetric],
    checkins_map: dict[str, DailyCheckIn],
    baseline_start: str,
    baseline_end: str,
    treatment_start: str,
    treatment_end: str,
) -> list[ConfounderCheck]:
    checks: list[ConfounderCheck] = []
    for path in confounder_paths:
        source = "checkin" if path.startswith("checkin.") else "metric"

        baseline_data = _extract_confounder(
            metrics_map, checkins_map, path, baseline_start, baseline_end,
        )
        treatment_data = _extract_confounder(
            metrics_map, checkins_map, path, treatment_start, treatment_end,
        )

        if isinstance(baseline_data, tuple) and isinstance(treatment_data, tuple):
            baseline_flags, baseline_total = baseline_data
            treatment_flags, treatment_total = treatment_data
            baseline_rate = baseline_flags / baseline_total if baseline_total else 0
            treatment_rate = treatment_flags / treatment_total if treatment_total else 0
            delta = treatment_rate - baseline_rate
            is_significant = abs(delta) > _CONFOUNDER_FLAG_THRESHOLD
            field_name = path.split(".")[-1].replace("_flag", "").replace("_", " ")
            note = (
                f"{field_name}: {treatment_flags}/{treatment_total} days in treatment "
                f"vs {baseline_flags}/{baseline_total} in baseline"
            )
            checks.append(
                ConfounderCheck(
                    path=path,
                    source=source,
                    baseline_mean=round(baseline_rate, 3),
                    treatment_mean=round(treatment_rate, 3),
                    delta_pct=round(delta * 100, 1),
                    is_significant=is_significant,
                    note=note,
                    baseline_flag_days=baseline_flags,
                    treatment_flag_days=treatment_flags,
                    baseline_total_days=baseline_total,
                    treatment_total_days=treatment_total,
                )
            )
        elif isinstance(baseline_data, list) and isinstance(treatment_data, list):
            baseline_mean = float(np.mean(baseline_data)) if baseline_data else None
            treatment_mean = float(np.mean(treatment_data)) if treatment_data else None
            delta_pct = None
            is_significant = False
            if baseline_mean is not None and treatment_mean is not None and baseline_mean != 0:
                delta_pct = round(
                    (treatment_mean - baseline_mean) / baseline_mean * 100, 1,
                )
                is_significant = abs(delta_pct) > _CONFOUNDER_NUMERIC_THRESHOLD
                if len(baseline_data) >= 2 and len(treatment_data) >= 2:
                    is_significant = (
                        is_significant
                        or welch_t_test(baseline_data, treatment_data) < _P_MODERATE
                    )

            note = f"{path}: " + (
                f"{round(treatment_mean, 1)} vs {round(baseline_mean, 1)} baseline"
                if baseline_mean is not None and treatment_mean is not None
                else "insufficient data"
            )
            checks.append(
                ConfounderCheck(
                    path=path,
                    source=source,
                    baseline_mean=round(baseline_mean, 2)
                    if baseline_mean is not None
                    else None,
                    treatment_mean=round(treatment_mean, 2)
                    if treatment_mean is not None
                    else None,
                    delta_pct=delta_pct,
                    is_significant=is_significant,
                    note=note,
                )
            )

    return checks
