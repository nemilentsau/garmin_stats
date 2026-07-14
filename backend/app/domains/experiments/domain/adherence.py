"""Experiment adherence summaries derived from exposure rows.

Adherence is calculated at experiment-day grain from exposure records, not from
individual activity records. Missing days remain explicit as unknown calendar
entries so the UI can distinguish no exposure from no scheduled treatment.
"""

from __future__ import annotations

from app.domains.experiments.contracts import AdherenceDayEntry, ExperimentExposure

from .windows import date_range


def compute_adherence(
    exposures: list[ExperimentExposure],
    treatment_start: str,
    treatment_end: str,
) -> tuple[float, list[AdherenceDayEntry]]:
    """Compute adherence rate and per-day calendar for a treatment window."""
    exposure_map = {exposure.date: exposure for exposure in exposures}

    entries: list[AdherenceDayEntry] = []
    full_count = 0

    for day in date_range(treatment_start, treatment_end):
        exposure = exposure_map.get(day)
        if exposure is not None:
            entries.append(
                AdherenceDayEntry(
                    date=day,
                    state=exposure.adherence_state,
                    exposure_score=exposure.exposure_score,
                )
            )
            if exposure.adherence_state == "full":
                full_count += 1
        else:
            entries.append(AdherenceDayEntry(date=day, state="unknown"))

    rate = full_count / len(entries) if entries else 0.0
    return round(rate, 3), entries
