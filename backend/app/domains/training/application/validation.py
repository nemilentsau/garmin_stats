"""L1-L12 block validator ported from `docs/routine-pivot/block0/linter.py`.

Owns the rule set that judges a compiled v3 block: tissue ownership (L2),
weekly time budgets (L3), prose-conditional prescriptions (L4), scheduling
constraints (L5), signal-closure and measurement integrity (L6), state-vector
capture coverage (L7), load-unit resolvability (L8), measurement-block
identity coherence (L9), anti-theater variant checks (L10), week-1 novelty
(L11), and exit-criteria presence (L12) — plus the residual part of L1 that
Task 1's typed contracts don't already enforce. `lint()` is the single entry
point; it never mutates its inputs and never touches the filesystem.

Three deltas from `linter.py`, each intentional:

1. **L7 (hardened).** The shipped linter marks a state component "covered"
   the instant its estimator has any non-`cap.*` input, even if that input is
   itself an unresolved derived signal (e.g. `S4`'s `est.physique` takes
   `tonnage.upper.7d` and `bodyweight` — neither starts with `cap.`, so the
   original marks `S4` covered without ever checking whether a card actually
   captures the tonnage inputs). This port instead walks the estimator DAG
   transitively: a state is covered only if a `cap.*` field is *reachable*
   from its estimator's inputs (following signal-producing estimators, e.g.
   `tonnage.upper.7d` -> `est.upper_tonnage` -> `cap.set_log.push_a`) and that
   field is captured by a card in the compiled schedule. A visited-estimator
   set bounds the walk against cyclic DAGs. On the shipped block0 artifacts
   every state component is reachable this way, so the stricter rule still
   reports zero L7 errors — the hardening only changes behavior on content
   that relied on the bug.
2. **L11 (computed).** The shipped linter hardcodes `novel = 3` with a
   comment listing three novel elements. This port counts the actual number
   of distinct overload `adaptation` kinds among week-1 scheduled overload
   cards, so the warning tracks real content instead of a stale comment.
3. **Message prefixes preserved.** Every error/warning keeps the linter's
   `[L#][ERROR]`/`[L#][WARN ]` prefix so a report reads identically to the
   shipped `lint_report.json`, even though the rule bodies are now typed.

Beyond those three, several of the linter's field-presence checks are
structurally impossible once content is parsed through Task 1's typed
contracts and are dropped rather than kept as permanently-dead branches — the
same reasoning the brief applies to L1's per-kind `REQ` dict (a card that
lacks a contract-required field, e.g. `RampSpec.endpoint` or
`IntensityFloor.metric`, fails to parse into a `V3Card` at all, so the check
can never fire on validated input):

- L1: the `REQ` per-contract-kind field-presence table (Pydantic's
  discriminated `Contract` union already enforces it). The residual L1 checks
  kept here are the two genuinely cross-referential ones: unknown
  `state_ref`/`preserves` against the registry's state-vector ids, and
  unknown `card_id` references from assignments.
- L6: the "capture field missing `AnalysisContract`" check (`CaptureField.
  contract: AnalysisContract` is required). The cross-referential "capture
  references unknown estimator" check is kept.
- L8: the strength-prescription branch's `sets`/`reps`/`load` presence check
  (`ExercisePrescriptionSpec` requires all three). The segment-prescription
  branch's `duration_min`/`distance_mi` presence check is kept, since both
  fields are optional on `SegmentSpec`.
- L10: the "ramp without endpoint" and "maintenance intensity_floor missing
  metric" checks (`RampSpec.endpoint` and `IntensityFloor.metric` are
  required fields).
- L12: the "extension rule missing cap" check (`ExtensionRule.
  cap_total_extension_days` is required).

The linter also carries a few module-level names it defines but never
reads (`orphan_signals`, the unused `AMBIENT` tuple, `INTENSITY_KEYS`) — dead
code with no effect on `errors`/`warnings`. They are not ported; keeping them
would trip this project's ruff `F841`/unused-name checks for no behavioral
gain.
"""

from __future__ import annotations

from collections import defaultdict
from re import IGNORECASE
from re import compile as re_compile
from typing import Any

from app.contracts.base import DefaultsRequired
from app.domains.training.application.compile import (
    SLOT_HOUR,
    CompiledEntry,
    cards_by_id,
    compile_schedule,
    entry_minutes,
    full_variant_prescription,
    seg_miles,
    week_of,
)
from app.domains.training.contracts import (
    AllPredicate,
    AnyPredicate,
    Cmp,
    EstimatorDef,
    ExerciseLibrary,
    ExercisePrescriptionSpec,
    ForbidSpec,
    MaintenanceContract,
    MeasurementContract,
    NotPredicate,
    OverloadContract,
    Predicate,
    Prescription,
    SignalRegistry,
    StrengthPrescription,
    V3Block,
    V3Bundle,
)

_BAD_NOTE = re_compile(r"\b(if|unless|only if|skip|instead|optional|coordinate)\b", IGNORECASE)

# Checks from the source linter that are structurally subsumed by the typed
# contracts (non-optional fields; validation fails before lint() is reachable):
#   L1 REQ per-kind contract fields  -> Contract union discriminates + requires them
#   L6 capture missing AnalysisContract -> CaptureField.contract is required
#   L8 strength sets/reps/load presence -> ExercisePrescriptionSpec requires them
#   L10 ramp-without-endpoint           -> RampSpec.endpoint is required
#   L10 intensity_floor missing metric  -> IntensityFloor.metric is required
#   L12 extension rule missing cap      -> ExtensionRule.cap_total_extension_days is required
# If any of these contract fields is ever loosened to optional, reinstate the
# corresponding lint check here.


class LintReport(DefaultsRequired):
    """L1-L12 findings plus the weekly rollups the block's budgets are checked against."""

    errors: list[str] = []
    warnings: list[str] = []
    week_run_miles: dict[int, float] = {}
    week_minutes_by_bundle: dict[int, dict[str, float]] = {}


def _exercises(prescription: Prescription) -> list[ExercisePrescriptionSpec]:
    return prescription.exercises if isinstance(prescription, StrengthPrescription) else []


def _load_resolvable(prescription: Prescription) -> bool:
    """L8: can `prescription` be rolled up into load units?

    A segment prescription resolves if every segment carries a duration or a
    distance. A strength prescription always resolves — `sets`/`reps`/`load`
    are required fields on `ExercisePrescriptionSpec` (see module docstring).
    """
    if isinstance(prescription, StrengthPrescription):
        return True
    return all(
        s.duration_min is not None or s.distance_mi is not None for s in prescription.segments
    )


def _walk_predicate(predicate: Predicate, consumed: set[str]) -> None:
    if isinstance(predicate, Cmp):
        consumed.add(predicate.signal)
    elif isinstance(predicate, AllPredicate):
        for clause in predicate.all:
            _walk_predicate(clause, consumed)
    elif isinstance(predicate, AnyPredicate):
        for clause in predicate.any:
            _walk_predicate(clause, consumed)
    elif isinstance(predicate, NotPredicate):
        _walk_predicate(predicate.not_, consumed)


def lint(
    block: V3Block, bundles: list[V3Bundle], registry: SignalRegistry, library: ExerciseLibrary
) -> LintReport:
    """Compile `bundles` against `block`/`registry` and run L1-L12.

    `library` mirrors the linter's `exlib` global: no L1-L12 rule reads it
    (the shipped linter never references `exlib` either), so it is accepted
    for interface symmetry with the other three artifacts and left unused.
    """
    del library
    errors: list[str] = []
    warnings: list[str] = []

    def err(rule: str, msg: str) -> None:
        errors.append(f"[{rule}][ERROR] {msg}")

    def warn(rule: str, msg: str) -> None:
        warnings.append(f"[{rule}][WARN ] {msg}")

    cards = cards_by_id(bundles)
    signals = {s.id for s in registry.signals}
    estimators = {e.id: e for e in registry.estimators}
    state_ids = {s.id for s in registry.state_vector}

    # ---------- L1: residual contract-completeness checks ----------
    for bundle in bundles:
        for assignment in bundle.assignments:
            if assignment.card_id not in cards:
                err(
                    "L1",
                    f"{bundle.id}: assignment day {assignment.day} references unknown card "
                    f"{assignment.card_id}",
                )
    for card_id, card in cards.items():
        state_ref: str | None = None
        if isinstance(card.contract, OverloadContract):
            state_ref = card.contract.state_ref
        elif isinstance(card.contract, MaintenanceContract):
            state_ref = card.contract.preserves
        if state_ref and state_ref not in state_ids:
            err("L1", f"{card_id}: contract references unknown state component {state_ref}")

    schedule = compile_schedule(bundles)

    # ---------- weekly rollups (feed L3 and L9, and the report) ----------
    week_run_miles_raw: dict[int, float] = defaultdict(float)
    week_minutes_raw: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for day in range(1, block.window.days + 1):
        run_mi = 0.0
        wk = week_of(day)
        for entry in (e for e in schedule if e.day == day):
            pres = full_variant_prescription(entry)
            if "segments" in pres and entry.bundle_id == "running.v3":
                run_mi += seg_miles(pres)
            week_minutes_raw[wk][entry.bundle_id] += entry_minutes(entry)
        week_run_miles_raw[wk] += run_mi

    # ---------- L2: ownership ----------
    tissue_owner: dict[str, str] = {}
    for bundle in bundles:
        for tissue in bundle.owns:
            if tissue in tissue_owner:
                err("L2", f"tissue {tissue} owned by both {tissue_owner[tissue]} and {bundle.id}")
            tissue_owner[tissue] = bundle.id
    for bundle in bundles:
        for card in bundle.cards:
            for exercise in _exercises(card.prescription):
                for tissue in exercise.targets:
                    owner = tissue_owner.get(tissue)
                    if owner is None:
                        err("L2", f"{card.id}: targets unowned tissue {tissue}")
                    elif owner != bundle.id:
                        err("L2", f"{card.id} ({bundle.id}) targets {tissue} owned by {owner}")

    # ---------- L3: budgets ----------
    for bundle in bundles:
        for budget in bundle.declared_budgets:
            for wk in range(1, 5):
                minutes = week_minutes_raw[wk].get(bundle.id, 0.0)
                if minutes > budget.minutes_max + 1e-6:
                    err(
                        "L3",
                        f"{bundle.id} week {wk}: scheduled {minutes:.0f} min > declared max "
                        f"{budget.minutes_max}",
                    )
                if budget.minutes_min and minutes < budget.minutes_min - 1e-6:
                    err(
                        "L3",
                        f"{bundle.id} week {wk}: scheduled {minutes:.0f} min < declared min "
                        f"{budget.minutes_min}",
                    )

    # ---------- L4: prose conditionals ----------
    for card_id, card in cards.items():
        note = card.display_notes or ""
        if note and _BAD_NOTE.search(note):
            err(
                "L4",
                f"{card_id}: display_notes contains conditional/coordination language: "
                f"'{note[:60]}...'",
            )

    # ---------- L5: scheduling constraints ----------
    def entries_matching(forbid: ForbidSpec) -> list[CompiledEntry]:
        out = []
        for entry in schedule:
            card = entry.card
            if forbid.contract_kind and card.contract.kind not in forbid.contract_kind:
                continue
            if forbid.targets:
                targeted: set[str] = set()
                for exercise in _exercises(card.prescription):
                    targeted.update(exercise.targets)
                if not targeted & set(forbid.targets):
                    continue
            out.append(entry)
        return out

    def hours(entry: CompiledEntry) -> float:
        return (entry.day - 1) * 24 + SLOT_HOUR.get(entry.slot, 12)

    for constraint in block.scheduling_constraints:
        reference = constraint.reference
        if reference.per_tissue_duplicate:
            per_day: dict[int, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
            for entry in schedule:
                if entry.card.contract.kind != "overload":
                    continue
                for exercise in _exercises(entry.card.prescription):
                    for tissue in exercise.targets:
                        per_day[entry.day][tissue].append(entry.card.id)
            for day, tissue_map in per_day.items():
                for tissue, card_ids in tissue_map.items():
                    if len(set(card_ids)) > 1:
                        err(
                            "L5",
                            f"{constraint.id}: day {day} tissue {tissue} targeted by multiple "
                            f"overloads {sorted(set(card_ids))}",
                        )
            continue
        refs = [e for e in schedule if e.card.id == reference.card_id]
        candidates = entries_matching(constraint.forbid)
        for ref_entry in refs:
            for candidate in candidates:
                if candidate is ref_entry or candidate.card.id == reference.card_id:
                    continue
                dt = hours(ref_entry) - hours(candidate)
                if (
                    constraint.relation == "within_hours_before"
                    and constraint.hours is not None
                    and 0 < dt <= constraint.hours
                ):
                    err(
                        "L5",
                        f"{constraint.id}: {candidate.card.id} (day {candidate.day} "
                        f"{candidate.slot}) within {constraint.hours}h before {ref_entry.card.id} "
                        f"(day {ref_entry.day})",
                    )
                if constraint.relation == "same_day_as" and candidate.day == ref_entry.day:
                    err(
                        "L5",
                        f"{constraint.id}: {candidate.card.id} same day as {ref_entry.card.id} "
                        f"(day {ref_entry.day})",
                    )

    # ---------- L6: measurement integrity + signal closure ----------
    for event in block.measurement_events:
        if event.required and not event.backup_days:
            err("L6", f"event {event.id}: required but no backup_days")
        if event.card_id not in cards:
            err("L6", f"event {event.id}: unknown card {event.card_id}")

    cap_fields: dict[str, list[str]] = defaultdict(list)
    for card_id, card in cards.items():
        for capture in card.capture:
            cap_fields[card_id].append(capture.id)
            if capture.contract.model_id not in estimators:
                err(
                    "L6",
                    f"{card_id}: capture {capture.id} references unknown estimator "
                    f"{capture.contract.model_id}",
                )
    for estimator in registry.estimators:
        if estimator.output_signal not in signals:
            err(
                "L6",
                f"estimator {estimator.id} outputs unregistered signal {estimator.output_signal}",
            )

    consumed: set[str] = set()
    for bundle in bundles:
        for assignment in bundle.assignments:
            for clause in assignment.selection.clauses:
                _walk_predicate(clause.when, consumed)
    for card in cards.values():
        if isinstance(card.contract, MeasurementContract):
            for gate in card.contract.quality_gate:
                _walk_predicate(gate, consumed)
    for criterion in block.exit_criteria:
        _walk_predicate(criterion.predicate, consumed)
    for constraint_spec in registry.objective.constraints:
        consumed.add(constraint_spec.signal)
    for state_component in registry.state_vector:
        consumed.add(state_component.signal)
    for review_spec in block.review_specs:
        for computed in review_spec.computed:
            if computed.estimator_id in estimators:
                consumed.add(estimators[computed.estimator_id].output_signal)
    for estimator in registry.estimators:
        for input_signal in estimator.inputs:
            if input_signal in signals:
                consumed.add(input_signal)

    strictly_orphan = {s for s in signals if s not in consumed}
    for signal in sorted(strictly_orphan):
        err(
            "L6",
            f"signal {signal} is never consumed by any rule, constraint, state, gate, "
            f"criterion, or review",
        )

    for estimator in registry.estimators:
        for input_signal in estimator.inputs:
            if input_signal.startswith("cap.") and "*" not in input_signal:
                captured = any(input_signal in ids for ids in cap_fields.values())
                if not captured:
                    err(
                        "L6",
                        f"estimator {estimator.id} input {input_signal} not captured by any card",
                    )

    # ---------- L7: state coverage (hardened, see module docstring) ----------
    scheduled_card_ids = {e.card.id for e in schedule}
    signal_producer: dict[str, EstimatorDef] = {e.output_signal: e for e in registry.estimators}

    def cap_captured_by_schedule(cap_id: str) -> bool:
        for card_id, ids in cap_fields.items():
            if card_id not in scheduled_card_ids:
                continue
            if cap_id in ids or any(cap_id.rstrip("*") in i for i in ids):
                return True
        return False

    def estimator_reaches_captured_cap(estimator: EstimatorDef, visited: set[str]) -> bool:
        if estimator.id in visited:
            return False
        visited.add(estimator.id)
        for input_signal in estimator.inputs:
            if input_signal.startswith("cap."):
                if cap_captured_by_schedule(input_signal):
                    return True
            elif input_signal in signal_producer and estimator_reaches_captured_cap(
                signal_producer[input_signal], visited
            ):
                return True
        return False

    for state_component in registry.state_vector:
        estimator = estimators.get(state_component.estimator_id)
        if not estimator:
            err(
                "L7",
                f"state {state_component.id}: unknown estimator {state_component.estimator_id}",
            )
            continue
        if not estimator_reaches_captured_cap(estimator, set()):
            err("L7", f"state {state_component.id} has no scheduled capture in this block")

    # ---------- L8: load rollup ----------
    for entry in schedule:
        if not _load_resolvable(entry.card.prescription):
            err("L8", f"{entry.card.id} day {entry.day}: prescription not resolvable to load units")

    # ---------- L9: identity coherence ----------
    if block.identity == "measurement":
        flat = [week_run_miles_raw.get(w, 0.0) for w in block.flat_weeks]
        if flat:
            mean = sum(flat) / len(flat)
            for week, miles in zip(block.flat_weeks, flat, strict=True):
                if abs(miles - mean) / mean > 0.03:
                    err(
                        "L9",
                        f"measurement block: week {week} run volume {miles:.1f} mi deviates >3% "
                        f"from flat mean {mean:.1f}",
                    )
        for card_id, card in cards.items():
            contract = card.contract
            if (
                isinstance(contract, OverloadContract)
                and contract.adaptation == "tendon_stiffness"
                and contract.ramp is None
            ):
                err(
                    "L9",
                    f"{card_id}: novel tendon overload in measurement block without declared ramp",
                )

    # ---------- L10: anti-theater ----------
    for bundle in bundles:
        for assignment in bundle.assignments:
            variant_ids = [v.id for v in assignment.variants]
            if "full" not in variant_ids:
                err("L10", f"{assignment.card_id} day {assignment.day}: no 'full' variant")
            if assignment.selection.default != "full":
                err(
                    "L10",
                    f"{assignment.card_id} day {assignment.day}: default path is "
                    f"'{assignment.selection.default}', must be 'full'",
                )
            for variant in assignment.variants:
                if variant.id == "skip":
                    continue
                if variant.stimulus_fraction < 0.5:
                    err(
                        "L10",
                        f"{assignment.card_id} day {assignment.day}: variant {variant.id} "
                        f"stimulus_fraction {variant.stimulus_fraction} < 0.5",
                    )
                if variant.id == "full" and variant.prescription_patch:
                    patch_segments: list[dict[str, Any]] = variant.prescription_patch.get(
                        "segments", []
                    )
                    for segment in patch_segments:
                        if set(segment.keys()) & {"intensity"}:
                            err(
                                "L10",
                                f"{assignment.card_id} day {assignment.day}: full-variant patch "
                                f"modifies intensity",
                            )
            for clause in assignment.selection.clauses:
                if clause.select == "plus":
                    err(
                        "L10",
                        f"{assignment.card_id} day {assignment.day}: rule selects 'plus'; plus is "
                        f"override-only",
                    )

    # ---------- L11: novelty (computed, see module docstring) ----------
    week1_adaptations: set[str] = set()
    for entry in schedule:
        if week_of(entry.day) != 1:
            continue
        if isinstance(entry.card.contract, OverloadContract):
            week1_adaptations.add(entry.card.contract.adaptation)
    novel = len(week1_adaptations)
    if novel > 2 and "protocol-change" not in block.baseline_tags:
        warn("L11", "week 1 introduces >2 novel elements without protocol-change tag")

    # ---------- L12: exit criteria ----------
    if not block.exit_criteria:
        err("L12", "block missing exit_criteria")
    if block.identity == "measurement" and not block.extension_rules:
        err("L12", "measurement block missing extension_rules")

    week_run_miles = {w: round(m, 1) for w, m in sorted(week_run_miles_raw.items())}
    week_minutes_by_bundle = {
        w: {bundle_id: float(round(minutes)) for bundle_id, minutes in bundle_minutes.items()}
        for w, bundle_minutes in sorted(week_minutes_raw.items())
    }
    return LintReport(
        errors=errors,
        warnings=warnings,
        week_run_miles=week_run_miles,
        week_minutes_by_bundle=week_minutes_by_bundle,
    )
