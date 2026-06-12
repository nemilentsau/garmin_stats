"""Correlation-deflated, recovery-signed weighting of the seven axis metrics.

Weighting inside the axis is practically immaterial (run
2026-06-11-recovery-score-weighting: equal, correlation-deflated, and PC1 weightings
agree at Spearman r >= 0.9996). Correlation-deflated weights are adopted for their
explicit double-count defense. Signs make every metric "recovery-positive" (higher =
better recovery), so the resting-HR/HR-avg/stress/respiration stress-pole is negated.
The composite needs at least 5 of 7 present inputs; weights renormalize over whatever
is present that day (the R3 missing-data rule).
"""

from __future__ import annotations

MIN_INPUTS = 5

RECOVERY_SIGNS: dict[str, int] = {
    "heart_rate_resting": -1,
    "heart_rate_avg": -1,
    "stress_avg": -1,
    "respiration_avg": -1,
    "body_battery_avg": +1,
    "hrv_nightly_avg": +1,
    "sleep_score": +1,
}

DEFLATED_WEIGHTS: dict[str, float] = {
    "heart_rate_resting": 0.142,
    "heart_rate_avg": 0.148,
    "stress_avg": 0.139,
    "respiration_avg": 0.137,
    "body_battery_avg": 0.135,
    "hrv_nightly_avg": 0.140,
    "sleep_score": 0.159,
}


def weighted_recovery_score(raw_z: dict[str, float | None]) -> tuple[float | None, int]:
    """Recovery-signed weighted mean of present per-metric z's; None if < 5 present.

    Accepts RAW (un-signed) per-metric z keyed by metric name; applies RECOVERY_SIGNS
    here so callers can pass normalization output directly. Returns (score, n_present);
    score is None when fewer than MIN_INPUTS metrics are present, but n_present is
    always the real count (so callers can flag a degraded day).
    """
    present = {
        key: value
        for key, value in raw_z.items()
        if value is not None and key in DEFLATED_WEIGHTS
    }
    if len(present) < MIN_INPUTS:
        return None, len(present)
    numerator = sum(
        RECOVERY_SIGNS[key] * value * DEFLATED_WEIGHTS[key]
        for key, value in present.items()
    )
    denominator = sum(DEFLATED_WEIGHTS[key] for key in present)
    return numerator / denominator, len(present)
