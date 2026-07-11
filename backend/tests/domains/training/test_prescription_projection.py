"""Structured-load and exercise-display projections for the workout-card redesign.

Covers Phase 0 Tasks 0.1-0.2 of the workout-card redesign — the seam that will
let the frontend render aligned load/target columns instead of parsing
`render_scheme`'s flattened display string.
"""

from __future__ import annotations

from app.domains.training.application.read_models import (
    build_exercise_display,
    last_logged_for,
    structured_load,
)
from app.domains.training.contracts import (
    ExercisePrescriptionSpec,
    LoadSpec,
    TrainingCaptureLog,
    TrainingCardLog,
    TrainingExerciseLog,
    TrainingLastLogged,
    TrainingSetLog,
)


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


def test_exercise_display_passes_through_a_real_last_logged_value():
    """Locks a Task 0.2 review Minor: a non-None `last` must reach the display verbatim."""
    ex = ExercisePrescriptionSpec(
        exercise_id="barbell_bench",
        targets=["upper_push"],
        sets=4,
        reps=(5, 8),
        load=LoadSpec(rpe=8),
        logging="set_rep_load",
    )
    last = TrainingLastLogged(weight_kg=95, reps=6, date="2026-07-09")
    d = build_exercise_display(ex, name="X", log_sets=True, last=last)
    assert d.last is not None
    assert d.last.date == "2026-07-09"


# ---------- last_logged_for ----------


def _log(date: str, exercise_id: str, *, weight: float, reps: int) -> TrainingCardLog:
    """Build a minimal completed card log with one logged set for `exercise_id`."""
    return TrainingCardLog(
        id=f"{date}:x",
        date=date,
        occurrence_key="x",
        status="completed",
        capture=TrainingCaptureLog(
            set_logs=[
                TrainingExerciseLog(
                    exercise_id=exercise_id,
                    sets=[TrainingSetLog(set_index=1, weight=weight, reps=reps)],
                )
            ]
        ),
    )


def test_last_logged_returns_most_recent_set_for_exercise():
    logs = [
        _log("2026-07-06", "barbell_bench", weight=90, reps=8),
        _log("2026-07-09", "barbell_bench", weight=95, reps=6),
    ]
    got = last_logged_for(logs, exercise_id="barbell_bench", before="2026-07-11")
    assert got is not None
    assert (got.weight_kg, got.reps, got.date) == (95.0, 6, "2026-07-09")
    assert last_logged_for(logs, exercise_id="never", before="2026-07-11") is None


def test_last_logged_returns_none_with_no_prior_logs():
    assert last_logged_for([], exercise_id="barbell_bench", before="2026-07-11") is None


def test_last_logged_returns_none_for_exercise_never_logged():
    logs = [_log("2026-07-06", "barbell_bench", weight=90, reps=8)]
    assert last_logged_for(logs, exercise_id="goblet_squat", before="2026-07-11") is None


def test_last_logged_picks_latest_date_among_multiple_prior_logs():
    logs = [
        _log("2026-07-01", "barbell_bench", weight=80, reps=8),
        _log("2026-07-09", "barbell_bench", weight=95, reps=6),
        _log("2026-07-06", "barbell_bench", weight=90, reps=8),
    ]
    got = last_logged_for(logs, exercise_id="barbell_bench", before="2026-07-11")
    assert got is not None
    assert (got.weight_kg, got.date) == (95.0, "2026-07-09")


def test_last_logged_ignores_logs_on_or_after_the_before_date():
    logs = [_log("2026-07-11", "barbell_bench", weight=100, reps=5)]
    assert last_logged_for(logs, exercise_id="barbell_bench", before="2026-07-11") is None
