"""Seeded trailing 7-day moving average for the displayed recovery trend.

Compute the MA over seed + display, then drop the seed days, so the first displayed
points use the 6 days before the window instead of ramping up from a single point.
Mirrors the dashboard `_MA_SEED_DAYS` precedent. The MA7 window is validated in run
2026-06-11-recovery-score-smoothing-spec (86% plateau-noise reduction, 0 added lag to
regime-onset detection, sustained regime depth preserved; MA3 too jagged, MA14
over-smooths). None values inside a window are skipped, not treated as zero.
"""

from __future__ import annotations

from app.utils.numeric import safe_avg

WINDOW = 7
SEED_DAYS = WINDOW - 1


def seeded_ma7(
    seed: list[float | None],
    display: list[float | None],
) -> list[float | None]:
    """Trailing 7-day MA over seed + display, returning only the display portion."""
    combined = list(seed) + list(display)
    smoothed: list[float | None] = []
    for index in range(len(combined)):
        window = [
            value
            for value in combined[max(0, index - SEED_DAYS): index + 1]
            if value is not None
        ]
        smoothed.append(safe_avg(window))
    return smoothed[len(seed):]
