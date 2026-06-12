"""Seeded trailing 7-day moving average for the displayed recovery trend.

Compute the MA over seed + display, then drop the seed days, so the first displayed
points use the 6 days before the window instead of ramping up from a single point.
Mirrors the dashboard `_MA_SEED_DAYS` precedent. The MA7 window is validated in run
2026-06-11-recovery-score-smoothing-spec (86% plateau-noise reduction, 0 added lag to
regime-onset detection, sustained regime depth preserved; MA3 too jagged, MA14
over-smooths). None values inside a window are skipped, not treated as zero.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.domains.garmin_analytics.domain.primitives.trends import trailing_ma7

WINDOW = 7
SEED_DAYS = WINDOW - 1


def seeded_ma7(
    seed: Sequence[float | None],
    display: Sequence[float | None],
) -> list[float | None]:
    """Trailing 7-day MA over seed + display, returning only the display portion.

    Delegates the windowing to the canonical `trailing_ma7` (same 7-day, None-skipping
    window); the seed days only exist to fill the left edge and are dropped from the
    result.
    """
    return trailing_ma7(list(seed) + list(display))[len(seed):]
