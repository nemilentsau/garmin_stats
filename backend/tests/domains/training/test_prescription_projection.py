"""Structured-load projection: the single present load dimension off a `LoadSpec`.

Covers Phase 0 Task 0.1 of the workout-card redesign — the seam that will let
the frontend render aligned load columns instead of parsing `render_scheme`'s
flattened display string.
"""

from __future__ import annotations

from app.domains.training.application.read_models import structured_load
from app.domains.training.contracts import LoadSpec


def test_structured_load_picks_the_single_present_field():
    assert structured_load(LoadSpec(pct_e1rm=0.87)) == ("pct_e1rm", 0.87)
    assert structured_load(LoadSpec(rpe=8)) == ("rpe", 8.0)
    assert structured_load(LoadSpec(absolute_kg=52)) == ("absolute_kg", 52.0)
    assert structured_load(LoadSpec()) == (None, None)
