"""Seeded trailing moving-average and dispersion-band wrappers for the recovery trend.

Owns two smoothers: (1) a 7-day MA center line and (2) a 14-day SD dispersion band.
Both use the same seeding pattern — compute over seed + display, then drop the seed
days, so the first displayed points use the preceding days instead of ramping up from
a single point. Mirrors the dashboard `_MA_SEED_DAYS` precedent. The MA7 window is
validated in run 2026-06-11-recovery-score-smoothing-spec (86% plateau-noise reduction,
0 added lag to regime-onset detection, sustained regime depth preserved; MA3 too jagged,
MA14 over-smooths). None values inside a window are skipped, not treated as zero.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.domains.garmin_analytics.domain.primitives.trends import (
    trailing_ma7,
    trailing_sd,
)

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


BAND_WINDOW = 14
BAND_SEED_DAYS = BAND_WINDOW - 1  # consumed by evidence.py for left-edge band seeding
BAND_MIN_VALID = 5  # >= a near-full week; trailing_sd needs >= 2 for ddof=1


def seeded_sd(
    seed: Sequence[float | None],
    display: Sequence[float | None],
) -> list[float | None]:
    """Trailing 14-day sample SD over seed + display, returning the display portion.

    The band width uses a longer window than the 7-day average center: a 14-day SD
    is a far steadier second-moment estimate, so the dispersion band reads as a calm
    ribbon instead of breathing day to day. The seed only fills the left edge and is
    dropped from the result, exactly like `seeded_ma7`.
    """
    return trailing_sd(
        list(seed) + list(display), BAND_WINDOW, BAND_MIN_VALID
    )[len(seed):]
