"""Detect sustained recovery regimes from the smoothed score, for trajectory annotation.

A "regime" is a sustained excursion of the MA7 recovery score outside the typical
band (|z| > 0.5) — a stretch of persistently low or elevated recovery. These are
DETECTED from the score series each render, not hard-coded, so they generalize to any
data, user, or future period. Brief returns into the band (<= a few days) do not split
a regime; runs shorter than the minimum are ignored as noise.

This is presentation annotation derived from the score, not a promoted FINDINGS claim;
it carries no causal interpretation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .thresholds import _BAND as BAND  # single source of truth for the typical-band edge

MIN_RUN_DAYS = 14
MERGE_GAP_DAYS = 3


@dataclass(frozen=True, slots=True)
class Regime:
    start: str
    end: str
    kind: str  # "low" | "elevated"
    label: str


def _runs(flags: Sequence[bool]) -> list[tuple[int, int]]:
    """Maximal index runs where flag is True, merging gaps <= MERGE_GAP_DAYS."""
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for i, on in enumerate(flags):
        if on and start is None:
            start = i
        elif not on and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(flags) - 1))

    if not runs:
        return []
    merged = [runs[0]]
    for s, e in runs[1:]:
        ps, pe = merged[-1]
        if s - pe - 1 <= MERGE_GAP_DAYS:
            merged[-1] = (ps, e)
        else:
            merged.append((s, e))
    return merged


def detect_regimes(
    dates: Sequence[str],
    ma7: Sequence[float | None],
) -> list[Regime]:
    """Sustained low (<= -0.5) and elevated (>= +0.5) MA7 runs of >= 14 days."""
    regimes: list[Regime] = []
    for kind, label, predicate in (
        ("low", "low recovery", lambda v: v <= -BAND),
        ("elevated", "elevated recovery", lambda v: v >= BAND),
    ):
        flags = [v is not None and predicate(v) for v in ma7]
        for start, end in _runs(flags):
            if end - start + 1 >= MIN_RUN_DAYS:
                regimes.append(
                    Regime(start=dates[start], end=dates[end], kind=kind, label=label)
                )
    regimes.sort(key=lambda r: r.start)
    return regimes
