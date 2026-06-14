"""Health flags: low-oxygen (spo2_avg) and thermoregulation (skin-temp deviation).

Personal robust thresholds (median +- 2.5*MAD); oxygen is one-sided low, thermo is
two-sided. A missing reading is a distinct "unknown" status, never "normal" — the SpO2
gaps are structural (two device-coverage blocks), not health events. Validated in run
2026-06-11-spo2-skintemp-flag-thresholds: spo2_avg beats spo2_min as the flag metric
(it catches the whole low-oxygen episode as a block), and the personal ~90.5%
threshold lands near the conventional 90% reference. Absolute cutoffs are useless here
(this user's nightly minimum runs ~80%), so the flag must be personal.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from app.utils.numeric import robust_center_scale

K = 2.5
_MIN_HISTORY = 30
OxygenRuleStatus = Literal["normal", "low", "unknown"]
ThermoregulationRuleStatus = Literal["normal", "below_usual", "above_usual", "unknown"]


def _robust_center_scale(history: Sequence[float | None]) -> tuple[float, float] | None:
    """Median and MAD-derived scale of the present history; None if too short.

    Delegates the median/MAD math to the shared `robust_center_scale`; this wrapper owns
    only the present-filtering and the flag domain's minimum-history policy.
    """
    values = [h for h in history if h is not None]
    if len(values) < _MIN_HISTORY:
        return None
    return robust_center_scale(values)


def oxygen_flag_status(
    value: float | None,
    *,
    history: Sequence[float | None],
) -> tuple[OxygenRuleStatus, float | None]:
    """Low-oxygen flag from nightly spo2_avg vs the personal lower threshold.

    Returns (status, threshold). A missing value is "unknown" (never "normal"); with
    too little history the oxygen status stays "normal" with no threshold.
    """
    center_scale = _robust_center_scale(history)
    threshold = (
        center_scale[0] - K * center_scale[1] if center_scale is not None else None
    )
    if value is None:
        return "unknown", threshold
    if threshold is None:
        return "normal", None
    return ("low" if value < threshold else "normal"), threshold


def thermo_flag_status(
    value: float | None,
    *,
    history: Sequence[float | None],
) -> tuple[ThermoregulationRuleStatus, tuple[float, float] | None]:
    """Thermoregulation flag from skin-temp deviation vs a two-sided personal band.

    Returns (status, (low, high)). A missing value is "unknown"; with too little
    history the thermoregulation status stays "normal" with no band.
    """
    center_scale = _robust_center_scale(history)
    band = (
        (center_scale[0] - K * center_scale[1], center_scale[0] + K * center_scale[1])
        if center_scale is not None
        else None
    )
    if value is None:
        return "unknown", band
    if band is None:
        return "normal", None
    low, high = band
    if value < low:
        return "below_usual", band
    if value > high:
        return "above_usual", band
    return "normal", band


def structural_gaps(
    dates: Sequence[str],
    present: Sequence[bool],
    *,
    min_len: int = 3,
) -> list[tuple[str, str]]:
    """Contiguous absent runs of >= min_len days, as (start, end) date pairs.

    Used to render SpO2 coverage gaps as explicit "no data" spans rather than letting a
    line bridge them. Singleton/short absences are not gaps.
    """
    gaps: list[tuple[str, str]] = []
    start: int | None = None
    for index, ok in enumerate(present):
        if not ok and start is None:
            start = index
        elif ok and start is not None:
            if index - start >= min_len:
                gaps.append((dates[start], dates[index - 1]))
            start = None
    if start is not None and len(present) - start >= min_len:
        gaps.append((dates[start], dates[-1]))
    return gaps
