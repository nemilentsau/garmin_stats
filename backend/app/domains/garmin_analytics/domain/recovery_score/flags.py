"""Health flags: low-oxygen (spo2_avg) and thermoregulation (skin-temp deviation).

Personal robust thresholds (median +- 2.5*MAD); oxygen is one-sided low, thermo is
two-sided. A missing reading is a distinct "unknown" state, never "clear" — the SpO2
gaps are structural (two device-coverage blocks), not health events. Validated in run
2026-06-11-spo2-skintemp-flag-thresholds: spo2_avg beats spo2_min as the flag metric
(it catches the whole low-oxygen episode as a block), and the personal ~90.5%
threshold lands near the conventional 90% reference. Absolute cutoffs are useless here
(this user's nightly minimum runs ~80%), so the flag must be personal.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

K = 2.5
_MAD_SCALE = 1.4826
_MIN_HISTORY = 30


def _robust_center_scale(history: Sequence[float | None]) -> tuple[float, float] | None:
    """Median and MAD-derived scale of the present history; None if too short."""
    values = np.array([h for h in history if h is not None], dtype=float)
    if len(values) < _MIN_HISTORY:
        return None
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median))) * _MAD_SCALE
    scale = mad if mad > 1e-9 else (float(np.std(values)) or 1e-9)
    return median, scale


def oxygen_flag_state(
    value: float | None,
    *,
    history: Sequence[float | None],
) -> tuple[str, float | None]:
    """Low-oxygen flag from nightly spo2_avg vs the personal lower threshold.

    Returns (state, threshold). A missing value is "unknown" (never "clear"); with too
    little history the flag stays "clear" with no threshold.
    """
    center_scale = _robust_center_scale(history)
    threshold = (
        center_scale[0] - K * center_scale[1] if center_scale is not None else None
    )
    if value is None:
        return "unknown", threshold
    if threshold is None:
        return "clear", None
    return ("flag" if value < threshold else "clear"), threshold


def thermo_flag_state(
    value: float | None,
    *,
    history: Sequence[float | None],
) -> tuple[str, tuple[float, float] | None]:
    """Thermoregulation flag from skin-temp deviation vs a two-sided personal band.

    Returns (state, (low, high)). A missing value is "unknown"; with too little history
    the flag stays "clear" with no band.
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
        return "clear", None
    low, high = band
    return ("flag" if (value < low or value > high) else "clear"), band


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
