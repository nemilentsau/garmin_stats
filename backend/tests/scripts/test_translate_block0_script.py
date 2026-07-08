"""Regression tests for the Block 0 v3→v2 translator's rendering policy."""

from __future__ import annotations

import runpy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "translate_block0.py"


def _ns() -> dict:
    return runpy.run_path(str(SCRIPT), run_name="__not_main__")


def test_set_scheme_renders_reps_range_and_load():
    ns = _ns()
    assert ns["set_scheme"]({"sets": 4, "reps": [5, 8], "load": {"rpe": 8}}) == "4×5–8 @ RPE 8"
    x = {"sets": 2, "reps": [2, 3], "load": {"pct_e1rm": 0.85}}
    assert ns["set_scheme"](x) == "2×2–3 @ 85% e1RM"


def test_segment_prescription_joins_distance_and_intensity():
    ns = _ns()
    seg = {"label": "easy", "intensity": {"zone": "Z1-Z2"}, "distance_mi": 7}
    assert ns["seg_prescription"](seg) == "7 mi · Z1-Z2"


def test_segment_kind_maps_by_label():
    ns = _ns()
    assert ns["seg_kind"]("warmup jog") == "warmup"
    assert ns["seg_kind"]("strides 6x20s, full recovery") == "strides"
    assert ns["seg_kind"]("primer: pogos") == "strides"
    assert ns["seg_kind"]("30 min max sustainable effort") == "main"
    assert ns["seg_kind"]("cooldown") == "cooldown"


def test_rule_rendering_is_plain_english():
    ns = _ns()
    selection = {
        "clauses": [
            {"when": {"any": [{"signal": "flag.tissue.quad", "op": "==", "value": True},
                               {"signal": "hrv.dev_swc", "op": "<", "value": -1.5}]},
             "select": "skip"},
            {"when": {"signal": "soreness.quad", "op": ">=", "value": 2}, "select": "reduced"},
        ],
        "default": "full",
        "on_missing_signal": "select_conservative",
    }
    text = ns["render_rule"](selection, [])
    assert text == (
        "Skip if quad flag or HRV (SWC units) < -1.5; "
        "Reduced if quad soreness >= 2; otherwise full; missing data → conservative."
    )


def test_full_translation_matches_lint_report_and_counts():
    ns = _ns()
    bundle = ns["build_bundle"]()
    assert bundle["schema_version"] == 2
    assert len(bundle["card_templates"]) == 15
    routine = bundle["routine_specs"][0]
    assert routine["start_date"] == "2026-07-06"
    assert len(routine["assignments"]) == 88
    # weekly miles must reproduce the linted truth
    assert ns["weekly_miles"]() == {1: 49.0, 2: 49.5, 3: 49.0, 4: 32.8}
