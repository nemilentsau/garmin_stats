"""Schedule-compile + L1-L12 validator tests against the block0 canon artifacts.

`test_block0_artifacts_lint_clean_and_reproduce_shipped_report` is the
keystone: block0 is shipped as a clean (0 error, 0 warning) block, so the
port must reproduce `lint_report.json`'s `errors`, `warnings`, and
`week_run_miles` exactly. Every other test mutates a deep copy of one shipped
artifact — one rule, one violation — and asserts the corresponding rule id
appears in the report, per the one-test-per-branch discipline in
`.claude/skills/testing/SKILL.md`.
"""

from __future__ import annotations

import json

from app.domains.training.application.validation import lint
from app.domains.training.contracts import (
    ExerciseLibrary,
    SignalRegistry,
    V3Block,
    V3Bundle,
)
from tests._architecture import REPO_ROOT

BLOCK0 = REPO_ROOT / "docs" / "routine-pivot" / "block0"
_BUNDLE_FILES = {
    "running.v3": "running_v3.json",
    "strength.v3": "strength_v3.json",
    "support.v3": "support_v3.json",
}


def _load(name: str) -> dict:
    return json.loads((BLOCK0 / name).read_text(encoding="utf-8"))


def _block0_artifacts() -> tuple[V3Block, list[V3Bundle], SignalRegistry, ExerciseLibrary]:
    block = V3Block.model_validate(_load("block0.json"))
    bundles = [V3Bundle.model_validate(_load(filename)) for filename in _BUNDLE_FILES.values()]
    registry = SignalRegistry.model_validate(_load("registry.json"))
    library = ExerciseLibrary.model_validate(_load("exercise_library.json"))
    return block, bundles, registry, library


def _truncate_assignments(raw_bundle: dict, *, through_day: int) -> dict:
    """Drop assignments past a shortened block window."""
    raw_bundle["assignments"] = [
        assignment
        for assignment in raw_bundle["assignments"]
        if assignment["day"] <= through_day
    ]
    return raw_bundle


def _bundles_with_override(overrides: dict[str, dict]) -> list[V3Bundle]:
    """Parse the three bundles, substituting a mutated raw dict for the given ids."""
    return [
        V3Bundle.model_validate(overrides.get(bundle_id) or _load(filename))
        for bundle_id, filename in _BUNDLE_FILES.items()
    ]


def test_block0_artifacts_lint_clean_and_reproduce_shipped_report():
    block, bundles, registry, library = _block0_artifacts()
    report = lint(block, bundles, registry, library)
    assert report.errors == []
    assert report.warnings == []
    shipped = json.loads((BLOCK0 / "lint_report.json").read_text(encoding="utf-8"))
    assert report.week_run_miles == {int(k): v for k, v in shipped["week_run_miles"].items()}
    assert report.week_minutes_by_bundle == {
        int(week): {bundle_id: float(minutes) for bundle_id, minutes in bundle_minutes.items()}
        for week, bundle_minutes in shipped["week_minutes_by_bundle"].items()
    }


# ---------- L1: residual contract-completeness (unknown state_ref) ----------


def test_l1_unknown_state_ref_flags_error():
    block, _, registry, library = _block0_artifacts()
    raw_strength = _load("strength_v3.json")
    for card in raw_strength["cards"]:
        if card["id"] == "str.lower_a":
            card["contract"]["state_ref"] = "S99"
    bundles = _bundles_with_override({"strength.v3": raw_strength})
    report = lint(block, bundles, registry, library)
    assert any("L1" in e for e in report.errors)


# ---------- L2: tissue ownership ----------


def test_l2_duplicate_tissue_ownership_flags_error():
    block, _, registry, library = _block0_artifacts()
    raw_running = _load("running_v3.json")
    raw_running["owns"] = ["quad"]  # strength.v3 already owns "quad"
    bundles = _bundles_with_override({"running.v3": raw_running})
    report = lint(block, bundles, registry, library)
    assert any("L2" in e for e in report.errors)


# ---------- L3: weekly time budgets ----------


def test_l3_budget_exceeded_flags_error():
    block, _, registry, library = _block0_artifacts()
    raw_strength = _load("strength_v3.json")
    raw_strength["declared_budgets"][0]["minutes_max"] = 100
    bundles = _bundles_with_override({"strength.v3": raw_strength})
    report = lint(block, bundles, registry, library)
    assert any("L3" in e for e in report.errors)


def test_l3_checks_every_week_of_a_block_longer_than_four_weeks():
    """A 35-day block leaves week 5 unscheduled, violating support's declared min."""
    raw_block = _load("block0.json")
    raw_block["window"]["days"] = 35
    block = V3Block.model_validate(raw_block)
    _, bundles, registry, library = _block0_artifacts()
    report = lint(block, bundles, registry, library)
    assert [e for e in report.errors if "L3" in e and "week 5" in e]


def test_l3_ignores_weeks_beyond_a_block_shorter_than_four_weeks():
    """A 21-day block has no week 4, so a satisfied weekly min must stay clean."""
    raw_block = _load("block0.json")
    raw_block["window"]["days"] = 21
    block = V3Block.model_validate(raw_block)
    _, _, registry, library = _block0_artifacts()
    bundles = _bundles_with_override(
        {
            bundle_id: _truncate_assignments(_load(filename), through_day=21)
            for bundle_id, filename in _BUNDLE_FILES.items()
        }
    )
    report = lint(block, bundles, registry, library)
    assert [e for e in report.errors if "L3" in e] == []


# ---------- L4: prose conditionals in display_notes ----------


def test_l4_conditional_display_notes_flags_error():
    block, _, registry, library = _block0_artifacts()
    raw_running = _load("running_v3.json")
    raw_running["cards"][0]["display_notes"] = "skip if tired"
    bundles = _bundles_with_override({"running.v3": raw_running})
    report = lint(block, bundles, registry, library)
    assert any("L4" in e for e in report.errors)


# ---------- L5: scheduling constraints ----------


def test_l5_hsr_within_24h_of_lthr_test_flags_error():
    block, _, registry, library = _block0_artifacts()
    raw_support = _load("support_v3.json")
    for assignment in raw_support["assignments"]:
        if assignment["day"] == 2 and assignment["card_id"] == "sup.hsr_a":
            assignment["day"] = 11
            assignment["slot"] = "morning"
            break
    bundles = _bundles_with_override({"support.v3": raw_support})
    report = lint(block, bundles, registry, library)
    assert any("L5" in e for e in report.errors)


# ---------- L6: measurement integrity + signal closure ----------


def test_l6_unconsumed_signal_flags_error():
    block, bundles, _, library = _block0_artifacts()
    raw_registry = _load("registry.json")
    raw_registry["signals"].append(
        {"id": "test.orphan_signal", "units": "au", "source": "derived", "staleness_hours": 24}
    )
    registry = SignalRegistry.model_validate(raw_registry)
    report = lint(block, bundles, registry, library)
    assert any("L6" in e for e in report.errors)


def test_l6_required_event_without_backup_days_flags_error():
    raw_block = _load("block0.json")
    raw_block["measurement_events"][0]["backup_days"] = []
    block = V3Block.model_validate(raw_block)
    _, bundles, registry, library = _block0_artifacts()
    report = lint(block, bundles, registry, library)
    assert any("L6" in e for e in report.errors)


# ---------- L7: state coverage (hardened transitive check) ----------


def test_l7_hardened_transitive_check_flags_error():
    block, bundles, _, library = _block0_artifacts()
    raw_registry = _load("registry.json")
    for state_component in raw_registry["state_vector"]:
        if state_component["id"] == "S2":
            # est.strap_validity's only input is ambient (garmin.hr_stream_meta):
            # no cap.* field is transitively reachable, so S2 should end up
            # uncovered under the hardened check even though it isn't under
            # the buggy "any non-cap.* input covers" original.
            state_component["estimator_id"] = "est.strap_validity"
    registry = SignalRegistry.model_validate(raw_registry)
    report = lint(block, bundles, registry, library)
    assert any("L7" in e for e in report.errors)


# ---------- L8: load rollup ----------


def test_l8_unresolvable_prescription_flags_error():
    block, _, registry, library = _block0_artifacts()
    raw_running = _load("running_v3.json")
    for card in raw_running["cards"]:
        if card["id"] == "run.lthr_test":
            warmup = card["prescription"]["segments"][0]
            warmup.pop("duration_min", None)
            warmup.pop("distance_mi", None)
    bundles = _bundles_with_override({"running.v3": raw_running})
    report = lint(block, bundles, registry, library)
    assert any("L8" in e for e in report.errors)


# ---------- L9: identity coherence (flat-week deviation) ----------


def test_l9_flat_week_deviation_flags_error():
    block, _, registry, library = _block0_artifacts()
    raw_running = _load("running_v3.json")
    for assignment in raw_running["assignments"]:
        if assignment["day"] == 8 and assignment["card_id"] == "run.easy":
            assignment["variants"][0]["prescription_patch"]["segments"][0]["distance_mi"] = 9.0
    bundles = _bundles_with_override({"running.v3": raw_running})
    report = lint(block, bundles, registry, library)
    assert any("L9" in e for e in report.errors)


# ---------- L10: anti-theater ----------


def test_l10_non_full_default_flags_error():
    block, _, registry, library = _block0_artifacts()
    raw_running = _load("running_v3.json")
    raw_running["assignments"][0]["selection"]["default"] = "reduced"
    bundles = _bundles_with_override({"running.v3": raw_running})
    report = lint(block, bundles, registry, library)
    assert any("L10" in e for e in report.errors)


def test_l10_low_stimulus_fraction_flags_error():
    block, _, registry, library = _block0_artifacts()
    raw_running = _load("running_v3.json")
    raw_running["assignments"][0]["variants"][1]["stimulus_fraction"] = 0.4  # "reduced" variant
    bundles = _bundles_with_override({"running.v3": raw_running})
    report = lint(block, bundles, registry, library)
    assert any("L10" in e for e in report.errors)


def test_l10_rule_selecting_plus_flags_error():
    block, _, registry, library = _block0_artifacts()
    raw_strength = _load("strength_v3.json")
    raw_strength["assignments"][0]["selection"]["clauses"].append(
        {"when": {"signal": "hrv.dev_swc", "op": ">", "value": 2.0}, "select": "plus"}
    )
    bundles = _bundles_with_override({"strength.v3": raw_strength})
    report = lint(block, bundles, registry, library)
    assert any("L10" in e for e in report.errors)


# ---------- L11: week-1 novelty (computed) ----------


def test_l11_missing_protocol_change_tag_flags_warning():
    raw_block = _load("block0.json")
    raw_block["baseline_tags"] = [t for t in raw_block["baseline_tags"] if t != "protocol-change"]
    block = V3Block.model_validate(raw_block)
    _, bundles, registry, library = _block0_artifacts()
    report = lint(block, bundles, registry, library)
    assert any("L11" in w for w in report.warnings)


# ---------- L12: exit criteria ----------


def test_l12_empty_exit_criteria_flags_error():
    raw_block = _load("block0.json")
    raw_block["exit_criteria"] = []
    block = V3Block.model_validate(raw_block)
    _, bundles, registry, library = _block0_artifacts()
    report = lint(block, bundles, registry, library)
    assert any("L12" in e for e in report.errors)
