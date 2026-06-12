"""Meaningful-change thresholds, score band, and trend direction.

T7/T1 are the validated change thresholds from run
2026-06-11-recovery-score-meaningful-change: the default comparison is the 7-day mean
vs the prior 7-day mean (|delta7| >= T7 is a meaningful sustained change), with a
secondary single-day acute flag (|delta1| >= T1). The band cuts at +-0.5 z realize the
Q4.1 finding that recovery days are a continuum, not discrete states — the "state
banner" is a coarse band x trend label, never an invented physiological archetype.
"""

from __future__ import annotations

T7 = 0.97
T1 = 1.86
_BAND = 0.5


def is_meaningful_delta7(delta7_z: float) -> bool:
    """Whether a 7-day-vs-prior-7-day change clears the meaningful-change threshold."""
    return abs(delta7_z) >= T7


def is_acute_delta1(delta1_z: float) -> bool:
    """Whether a single-day change clears the acute threshold."""
    return abs(delta1_z) >= T1


def score_band(score_z: float) -> str:
    """Coarse band of the recovery score vs the personal baseline."""
    if score_z <= -_BAND:
        return "suppressed"
    if score_z >= _BAND:
        return "strong"
    return "typical"


def trend_direction(delta7_z: float) -> str:
    """Trend label from the 7-day change against the meaningful-change threshold."""
    if delta7_z >= T7:
        return "improving"
    if delta7_z <= -T7:
        return "declining"
    return "steady"
