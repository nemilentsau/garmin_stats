"""Structured-load and exercise-display projections for the workout-card redesign.

Covers Phase 0 Tasks 0.1-0.2 of the workout-card redesign — the seam that will
let the frontend render aligned load/target columns instead of parsing
`render_scheme`'s flattened display string.
"""

from __future__ import annotations

from app.domains.training.application.read_models import build_exercise_display, structured_load
from app.domains.training.contracts import ExercisePrescriptionSpec, LoadSpec


def test_structured_load_picks_the_single_present_field():
    assert structured_load(LoadSpec(pct_e1rm=0.87)) == ("pct_e1rm", 0.87)
    assert structured_load(LoadSpec(rpe=8)) == ("rpe", 8.0)
    assert structured_load(LoadSpec(absolute_kg=52)) == ("absolute_kg", 52.0)
    assert structured_load(LoadSpec()) == (None, None)


def test_exercise_display_carries_structured_fields():
    ex = ExercisePrescriptionSpec(
        exercise_id="barbell_bench",
        targets=["upper_push"],
        sets=4,
        reps=(5, 8),
        load=LoadSpec(rpe=8),
        tempo="top set then back-offs",
        logging="set_rep_load",
    )
    d = build_exercise_display(ex, name="Barbell Bench", log_sets=True, last=None)
    assert (d.sets, d.reps_low, d.reps_high) == (4, 5, 8)
    assert (d.load_kind, d.load_value) == ("rpe", 8.0)
    assert d.scheme == "4×5–8 @ RPE 8"  # back-compat preserved
    assert d.tempo == "top set then back-offs"
