"""Today/schedule-window/block-status read models plus capture-log upsert.

Owns the projection from typed v3 wire contracts and the compiled schedule
into the display-ready `Training*` view models
in `contracts.py`, merged with any saved `TrainingCardLog`. This module never
mutates a v3 artifact and never lints — `application/validation.py` already
ran (and blocked activation on failure) before anything here can observe an
active block, so every artifact this module reads is assumed schedule-valid.

Four small "render" helpers turn a typed prescription/rule/gate fragment into
one short display string: `render_scheme` (a strength exercise's sets/reps/
load), `render_segment` (a run/support segment's distance/duration/
intensity), `render_rule` (a card's variant-selection rule, in English), and
`render_gate` (a measurement card's quality gate). They are pure string
formatting with no I/O, kept here rather than in `contracts.py` so the wire
contracts stay free of display concerns.

The prescription-seam helpers build on that: `structured_load` picks
`render_scheme`'s same load dimension (`pct_e1rm` -> `rpe` -> `absolute_kg`)
but returns it as typed `(kind, value)` for the frontend to format instead of
a pre-rendered string; `build_exercise_display`/`build_segment_display` wrap
one prescribed exercise/segment into its full `TrainingExerciseDisplay`/
`TrainingSegmentDisplay` projection, string and structured fields together;
and `last_logged_for` scans a card's prior logs to find the most recent
logged set for one exercise, the "last" load anchor a lifter sees next to a
prescribed set. Only `get_training_today` computes a real anchor: it loads
prior-log history via `repo.card_logs_before(date)` and threads it as
`prior_logs` through `_cards_for_day` -> `_build_card`, which calls
`last_logged_for` per exercise. `get_training_schedule_window`'s planning
view calls the same `_cards_for_day`/`_build_card` path without `prior_logs`,
so every exercise's `last` is `None` there — a future day's card has no
"prior" log to anchor against.

`upsert_training_log` applies a partial update keyed off
`TrainingLogUpdateRequest.model_fields_set`: a field the caller omitted from
the request body keeps the existing log's value, while a field the caller
included — even as an explicit `null` — is applied, clearing it when the
value is `None`. It also
rejects capture PUTs against an occurrence the Today projection does not
display for the given date, raising `LookupError` (mapped to 404 by the
app-level exception handler) rather than persisting a log nothing will ever
display. This makes active authored backups writable without whitelisting
inactive backup keys.

Run<->prescription association is threaded through both Today and schedule
windows: `match_run_to_card` is the pure matching-policy
function (manual link wins; else auto-match only when exactly one
`running.v3` card is scheduled that day; see its docstring for the full
precedence), and `_build_card` calls it per run card using the day's tracked
runs and run-card count. Today and schedule windows each make one bulk summary
read covering the union of the visible range and authored opportunities
elapsed by the request's as-of date. Summaries are grouped by `session_date`;
authored opportunities are simulated in order and each backup decision is
frozen against assessments available strictly before that local day. A
separate as-of pass determines current actions, while visible cards use the
current latest assessment. `resolve_measurement_day` overlays any due backup
without changing the compiled schedule. `training`
never imports a Garmin contract or unit conversion for this — the port
(defined in `dependencies.py`) returns already-imperial, training-local
`TrainingRunActivitySummary` values; the adapter that implements it lives outside the slice
(`bootstrap/run_activity_port.py`), composed in by `bootstrap/container.py`.
`upsert_training_log` accepts the same port to validate a manually-set
`linked_run_id` at write time (`ValueError`, mapped to 400) — a stricter
check than the read-time policy, which tolerates a link that has since gone
stale.
"""

from __future__ import annotations

import re
from datetime import date as date_cls
from datetime import timedelta
from typing import Literal

from app.contracts.base import StrictDefaultsRequired
from app.domains.training.application.compile import (
    SLOT_HOUR,
    CompiledEntry,
    compile_schedule,
    full_variant_prescription,
    is_running_bundle,
    week_of,
)
from app.domains.training.application.measurement_schedule import (
    MeasurementBackupActivation,
    MeasurementDayResolution,
    resolve_measurement_day,
)
from app.domains.training.contracts import (
    AllPredicate,
    AnyPredicate,
    Cmp,
    ExerciseLibrary,
    ExercisePrescriptionSpec,
    LoadSpec,
    MeasurementContract,
    MeasurementStatus,
    NotPredicate,
    Predicate,
    SegmentSpec,
    SelectionRule,
    SignalRegistry,
    StrengthPrescription,
    TrainingBlockStatus,
    TrainingCaptureLog,
    TrainingCardLog,
    TrainingCardStatus,
    TrainingCheckinRow,
    TrainingExecutionEvaluation,
    TrainingExerciseDisplay,
    TrainingLastLogged,
    TrainingMeasurementAssessment,
    TrainingMeasurementEvaluation,
    TrainingRunActivitySummary,
    TrainingRunEvidence,
    TrainingScheduleDay,
    TrainingScheduleWindow,
    TrainingSegmentDisplay,
    TrainingTodayCard,
    TrainingTodayResponse,
    V3Block,
    V3Bundle,
)
from app.domains.training.dependencies import (
    MeasurementAssessmentReadPort,
    RunActivityReadPort,
    TrainingRepository,
)
from app.domains.training.domain.run_evaluation import (
    effective_execution,
    evaluate_run_measurement,
    finalize_measurement,
)

AssessmentCache = dict[
    tuple[str, str, str | None],
    TrainingMeasurementAssessment | None,
]

# ---------- signal short-names + predicate/render helpers ----------

_SIGNAL_LABELS: dict[str, str] = {
    "hrv.dev_swc": "HRV (SWC units)",
    "rhr.delta_7d": "RHR delta (bpm)",
    "sleep.score": "sleep score",
    "env.dew_point": "dew point (°F)",
}

_EVENT_COMPLETED_RE = re.compile(r"^event\.(.+)\.completed$")

_MISSING_SIGNAL_LABELS: dict[str, str] = {
    "select_conservative": "conservative",
    "select_default": "default",
    "ask": "ask",
}


def _signal_label(signal: str) -> str:
    """Map a registry signal id to its short English display name.

    Falls back to the raw signal id for signals outside the mapped set (e.g.
    `strap.validity_pct` in `run.lthr_test`'s quality gate) — good enough for
    a gate/rule footnote, not meant to cover every registered signal.
    """
    if signal in _SIGNAL_LABELS:
        return _SIGNAL_LABELS[signal]
    if signal.startswith("soreness."):
        return f"{signal.removeprefix('soreness.')} soreness"
    if signal.startswith("flag.tissue."):
        return f"{signal.removeprefix('flag.tissue.')} flag"
    match = _EVENT_COMPLETED_RE.match(signal)
    if match:
        return f"{match.group(1)} already completed"
    return signal


def _num(value: float | int) -> str:
    """Render a number without a trailing `.0` for whole values."""
    return str(int(value)) if float(value).is_integer() else str(value)


def _display_number(signal: str, value: float | int) -> str:
    """Render a numeric predicate value in the app's display units."""
    if signal == "env.dew_point":
        return f"{value * 9 / 5 + 32:.1f}"
    return _num(value)


def _cmp_phrase(cmp: Cmp) -> str:
    """English phrase for one leaf comparison.

    `signal == true`/`signal == false` collapse to the signal's own label
    (already phrased as an assertion, e.g. "quad flag") rather than
    "quad flag == True" — every other operator/value pair renders as
    "<label> <op> <value>".
    """
    label = _signal_label(cmp.signal)
    if cmp.op == "==" and cmp.value is True:
        return label
    if cmp.op == "==" and cmp.value is False:
        return f"not {label}"
    value = cmp.value
    if isinstance(value, bool):
        value_display = str(value)
    elif isinstance(value, (int, float)):
        value_display = _display_number(cmp.signal, value)
    else:
        value_display = str(value)
    return f"{label} {cmp.op} {value_display}"


def _predicate_phrase(predicate: Predicate) -> str:
    """Recursively render any predicate shape (`Cmp`/`all`/`any`/`not`) to English."""
    if isinstance(predicate, Cmp):
        return _cmp_phrase(predicate)
    if isinstance(predicate, AllPredicate):
        return " and ".join(_predicate_phrase(p) for p in predicate.all)
    if isinstance(predicate, AnyPredicate):
        return " or ".join(_predicate_phrase(p) for p in predicate.any)
    if isinstance(predicate, NotPredicate):
        return f"not ({_predicate_phrase(predicate.not_)})"
    raise TypeError(f"Unknown predicate type: {type(predicate)!r}")  # pragma: no cover


def structured_load(
    load: LoadSpec,
) -> tuple[Literal["pct_e1rm", "rpe", "absolute_kg"] | None, float | None]:
    """Return the single present load dimension as (kind, value).

    Mirrors `render_scheme`'s load precedence: pct_e1rm -> rpe -> absolute_kg.
    """
    if load.pct_e1rm is not None:
        return "pct_e1rm", float(load.pct_e1rm)
    if load.rpe is not None:
        return "rpe", float(load.rpe)
    if load.absolute_kg is not None:
        return "absolute_kg", float(load.absolute_kg)
    return None, None


def render_scheme(exercise: ExercisePrescriptionSpec) -> str:
    """Render a strength exercise's sets/reps/load as one compact scheme string.

    Load display picks the first present of `pct_e1rm` -> `rpe` ->
    `absolute_kg` and never combines two — e.g. `sets=3, reps=(2,3),
    load={pct_e1rm: 0.87, rpe: 8}` renders "3×2–3 @ 87% e1RM", not a compound
    string with both.
    """
    lo, hi = exercise.reps
    scheme = f"{exercise.sets}×{lo}–{hi}"
    load = exercise.load
    if load.pct_e1rm is not None:
        load_display = f"{round(load.pct_e1rm * 100)}% e1RM"
    elif load.rpe is not None:
        load_display = f"RPE {_num(load.rpe)}"
    elif load.absolute_kg is not None:
        load_display = f"{_num(load.absolute_kg)} kg"
    else:
        return scheme
    return f"{scheme} @ {load_display}"


def build_exercise_display(
    exercise: ExercisePrescriptionSpec,
    *,
    name: str,
    log_sets: bool,
    last: TrainingLastLogged | None,
) -> TrainingExerciseDisplay:
    """Project one prescribed exercise into its read-only display projection.

    ``scheme`` stays alongside the structured repetition/load fields for
    compatibility. ``last`` is supplied by the caller; this helper performs
    no history lookup.
    """
    lo, hi = exercise.reps
    kind, value = structured_load(exercise.load)
    return TrainingExerciseDisplay(
        exercise_id=exercise.exercise_id,
        name=name,
        scheme=render_scheme(exercise),
        tempo=exercise.tempo,
        sets=exercise.sets,
        log_sets=log_sets,
        reps_low=lo,
        reps_high=hi,
        load_kind=kind,
        load_value=value,
        last=last,
    )


def last_logged_for(
    logs: list[TrainingCardLog], *, exercise_id: str, before: str
) -> TrainingLastLogged | None:
    """Most recent logged set for `exercise_id` among `logs` dated strictly before `before`.

    Scans every log whose capture recorded a `TrainingExerciseLog` for
    `exercise_id`, keeps the latest-dated match, and returns the last set on
    that log with a non-`None` weight as the load anchor (a card can log
    warm-up sets with no weight after the working sets; those are skipped).
    Returns `None` when no prior log recorded this exercise at all, or when
    the latest matching log's sets carry no weight — both read as "no anchor
    yet" to the caller. When multiple prior logs share the same latest date
    for the exercise, `max` picks whichever candidate it encounters first for
    that date, which is deterministic by the adapter's `id`
    (`date:occurrence_key`) ordering but semantically arbitrary; current
    templates never log one exercise on two same-day cards, so this never
    actually happens.
    """
    candidates = [
        log
        for log in logs
        if log.date < before
        and log.capture is not None
        and any(exercise.exercise_id == exercise_id for exercise in log.capture.set_logs)
    ]
    if not candidates:
        return None
    latest = max(candidates, key=lambda log: log.date)
    assert latest.capture is not None  # narrowed by the candidates filter above
    exercise_log = next(
        exercise for exercise in latest.capture.set_logs if exercise.exercise_id == exercise_id
    )
    weighted_sets = [set_log for set_log in exercise_log.sets if set_log.weight is not None]
    if not weighted_sets:
        return None
    last_set = weighted_sets[-1]
    return TrainingLastLogged(weight_kg=last_set.weight, reps=last_set.reps, date=latest.date)


def render_segment(segment: SegmentSpec) -> str:
    """Render a run/support segment's distance/duration/intensity as one line.

    Parts present are joined with " · "; intensity contributes at most one
    part, preferring zone -> rpe -> hr_range in that order.
    """
    parts: list[str] = []
    if segment.distance_mi:
        parts.append(f"{_num(segment.distance_mi)} mi")
    if segment.duration_min:
        parts.append(f"{_num(segment.duration_min)} min")
    intensity = segment.intensity
    if intensity.zone:
        parts.append(intensity.zone)
    elif intensity.rpe is not None:
        parts.append(f"RPE {_num(intensity.rpe)}")
    elif intensity.hr_range is not None:
        lo, hi = intensity.hr_range
        parts.append(f"{lo}–{hi} bpm")
    return " · ".join(parts)


def build_segment_display(segment: SegmentSpec) -> TrainingSegmentDisplay:
    """Project one prescribed run/support segment into its display projection.

    ``detail`` stays alongside structured distance/duration/zone fields for
    API compatibility.
    `zone` is `None` for rpe-only or hr_range-only segments (e.g. drills,
    strides, primers) — the frontend falls back to `detail` for those.
    """
    return TrainingSegmentDisplay(
        label=segment.label,
        detail=render_segment(segment),
        distance_mi=segment.distance_mi,
        duration_min=segment.duration_min,
        zone=segment.intensity.zone,
    )


def render_rule(selection: SelectionRule) -> str | None:
    """Render a card's variant-selection rule as one English sentence.

    Returns None when the rule has no clauses (an unconditional "always
    full" assignment, e.g. `sup.daily`) — the read model omits
    `rule_display` in that case rather than showing a trivial rule. Each
    clause renders as "<Select> if <predicate English>"; a shared tail
    states the unconditional default and the missing-signal fallback.
    """
    if not selection.clauses:
        return None
    clause_phrases = [
        f"{clause.select.capitalize()} if {_predicate_phrase(clause.when)}"
        for clause in selection.clauses
    ]
    missing = _MISSING_SIGNAL_LABELS.get(selection.on_missing_signal, selection.on_missing_signal)
    tail = f"otherwise {selection.default}; missing data → {missing}."
    return "; ".join([*clause_phrases, tail])


def render_gate(contract: MeasurementContract) -> str:
    """Render a measurement card's estimand plus quality gate as one display line."""
    gates = "; ".join(_predicate_phrase(gate) for gate in contract.quality_gate)
    return f"Measurement: {contract.estimand}. Gate: {gates}."


def checkin_rows(registry: SignalRegistry) -> list[TrainingCheckinRow]:
    """Build one check-in row per `soreness.*` signal in the registry.

    Row order follows the registry's own signal order; `label` humanizes the
    tissue id by replacing underscores with " / " (e.g. `tibialis_foot` ->
    "tibialis / foot").
    """
    rows: list[TrainingCheckinRow] = []
    for signal in registry.signals:
        if not signal.id.startswith("soreness."):
            continue
        tissue = signal.id.removeprefix("soreness.")
        rows.append(TrainingCheckinRow(tissue=tissue, label=tissue.replace("_", " / ")))
    return rows


# ---------- day math + active-context loading ----------


def _day_number(block: V3Block, date: str) -> int:
    """1-indexed block day for `date`; may fall outside `[1, window.days]`."""
    start = date_cls.fromisoformat(block.window.start)
    return (date_cls.fromisoformat(date) - start).days + 1


def _active_context(
    repo: TrainingRepository,
) -> tuple[V3Block, list[V3Bundle], SignalRegistry, ExerciseLibrary] | None:
    """Load and parse the active block plus its bundles/registry/library.

    Returns None when nothing is imported yet. All four artifact kinds are
    always imported together (`application/imports.py`'s single-shot
    activation), so an active block implies the other three are present.
    """
    stored_block = repo.active_block()
    if stored_block is None:
        return None
    block = V3Block.model_validate(stored_block.artifact)
    bundles = [V3Bundle.model_validate(b.artifact) for b in repo.bundles_for(block.bundle_ids)]
    stored_registry = repo.registry()
    stored_library = repo.library()
    assert stored_registry is not None
    assert stored_library is not None
    registry = SignalRegistry.model_validate(stored_registry.artifact)
    library = ExerciseLibrary.model_validate(stored_library.artifact)
    return block, bundles, registry, library


def _exercise_name(library: ExerciseLibrary, exercise_id: str) -> str:
    for exercise in library.exercises:
        if exercise.id == exercise_id:
            return exercise.name
    return exercise_id


# ---------- run<->prescription association ----------


def _prescribed_distance_mi(segments: list[TrainingSegmentDisplay]) -> float | None:
    """Sum of a run card's segment distances, or None when none prescribe one.

    Drill/strides primers routinely omit `distance_mi` on a segment (e.g. a
    "primer" or "drills" segment carries only `duration_min`); this only
    counts the segments that do, and returns None (not 0) when nothing in
    the card prescribes a distance at all — `match_run_to_card` reads that
    None as "no distance prescription", not "zero-distance prescription".
    """
    distances = [s.distance_mi for s in segments if s.distance_mi is not None]
    return sum(distances) if distances else None


def match_run_to_card(
    *,
    linked_run_id: str | None,
    run_link_detached: bool,
    prescribed_distance_mi: float | None,
    runs_today: list[TrainingRunActivitySummary],
    run_cards_today: int,
) -> TrainingRunActivitySummary | None:
    """Resolve one run card's associated tracked run for its scheduled day.

    Precedence, in order:

    1. A manual `linked_run_id` always wins, even over a `run_link_detached`
       flag also set on the same log — detaching only takes effect once the
       manual link itself is cleared (there is no state where both a
       specific link and "detached" are simultaneously in force). A
       `linked_run_id` absent from `runs_today` is a stale link (e.g. the
       run was re-ingested and changed id after the link was saved): it
       silently resolves to no association rather than raising — the
       caller still offers `runs_today` as re-pick candidates regardless of
       this function's result.
    2. `run_link_detached` with no manual link explicitly suppresses
       auto-matching for this occurrence.
    3. Otherwise, auto-match: only when exactly one run card is scheduled
       for the day (two or more run cards have no unambiguous per-card
       signal, so only a manual link can resolve them) and at least one run
       exists for the date. The pick is the run whose `distance_mi` is
       closest to `prescribed_distance_mi`; when the card prescribes no
       distance at all, the longest run wins instead. A run with no
       `distance_mi` of its own sorts as 0 mi in both comparisons.

    The returned summary's `link_source` reflects which branch resolved it
    ("manual" for 1, "auto" for 3); branches 1's stale-link case and 2 both
    return None rather than a summary, so `link_source` never needs a third
    value for "no match".
    """
    if linked_run_id is not None:
        match = next((run for run in runs_today if run.run_id == linked_run_id), None)
        return None if match is None else match.model_copy(update={"link_source": "manual"})
    if run_link_detached:
        return None

    if run_cards_today != 1 or not runs_today:
        return None
    if prescribed_distance_mi is None:
        chosen = max(runs_today, key=lambda run: run.distance_mi or 0.0)
    else:
        chosen = min(
            runs_today, key=lambda run: abs((run.distance_mi or 0.0) - prescribed_distance_mi)
        )
    return chosen.model_copy(update={"link_source": "auto"})


def _build_card(
    entry: CompiledEntry,
    *,
    date: str,
    registry: SignalRegistry,
    library: ExerciseLibrary,
    bundle_names: dict[str, str],
    block: V3Block,
    repo: TrainingRepository,
    prior_logs: list[TrainingCardLog] | None = None,
    runs_today: list[TrainingRunActivitySummary] | None = None,
    run_cards_today: int = 0,
    run_activity_port: RunActivityReadPort | None = None,
    measurement_assessment_port: MeasurementAssessmentReadPort | None = None,
    measurement_event_id: str | None = None,
    measurement_attempt: Literal["scheduled", "backup"] | None = None,
    occurrence_key_override: str | None = None,
    assessment_before: str | None = None,
    evidence_cache: dict[str, TrainingRunEvidence | None] | None = None,
    assessment_cache: AssessmentCache | None = None,
) -> TrainingTodayCard:
    """Project one compiled schedule entry into a display-ready Today card, log merged in.

    `prior_logs` feeds `last_logged_for` per exercise — the Today path
    (`get_training_today`) loads real history and passes it; the
    schedule-window path leaves it `None` (planning view, read-only), so
    `last` is always `None` there rather than looked up per rendered day.

    `runs_today`/`run_cards_today` carry the caller's preloaded summaries and
    this day's run-card count. Association (`match_run_to_card`) only runs for a
    training-classified running card — every other card gets
    `run_candidates=[]`, `associated_activity=None` unconditionally.
    The optional caches are request-owned snapshots; they include missing
    evidence and `None` assessments and never outlive the public read call.
    Assessment cache identity includes the optional historical cutoff.
    """
    card = entry.card
    assignment = entry.assignment
    occurrence_key = occurrence_key_override or (
        f"{entry.bundle_id}:{card.id}:d{entry.day:02d}"
    )

    segments: list[SegmentSpec] = []
    segments_display: list[TrainingSegmentDisplay] = []
    exercises_display: list[TrainingExerciseDisplay] = []
    log_sets = any(field.type == "set_rep_load[]" for field in card.capture)
    if isinstance(card.prescription, StrengthPrescription):
        exercises_display = [
            build_exercise_display(
                exercise,
                name=_exercise_name(library, exercise.exercise_id),
                log_sets=log_sets,
                last=last_logged_for(
                    prior_logs or [], exercise_id=exercise.exercise_id, before=date
                ),
            )
            for exercise in card.prescription.exercises
        ]
    else:
        patched = full_variant_prescription(entry)
        segments = [SegmentSpec.model_validate(raw) for raw in patched.get("segments", [])]
        segments_display = [build_segment_display(segment) for segment in segments]

    rows = (
        checkin_rows(registry)
        if any(field.id == "cap.checkin.soreness" for field in card.capture)
        else []
    )
    capture_rpe = any(field.type == "number" for field in card.capture)
    gate_display = (
        render_gate(card.contract) if isinstance(card.contract, MeasurementContract) else None
    )

    log = repo.card_log(date, occurrence_key)

    associated_activity: TrainingRunActivitySummary | None = None
    run_candidates: list[TrainingRunActivitySummary] = []
    if is_running_bundle(entry.bundle_id):
        run_candidates = runs_today or []
        associated_activity = match_run_to_card(
            linked_run_id=log.linked_run_id if log else None,
            run_link_detached=log.run_link_detached if log else False,
            prescribed_distance_mi=_prescribed_distance_mi(segments_display),
            runs_today=run_candidates,
            run_cards_today=run_cards_today,
        )

    execution: TrainingExecutionEvaluation = effective_execution(
        log_status=log.status if log else "pending",
        run_id=associated_activity.run_id if associated_activity else None,
    )
    measurement: TrainingMeasurementEvaluation | None = None
    if (
        associated_activity is not None
        and isinstance(card.contract, MeasurementContract)
        and run_activity_port is not None
    ):
        run_id = associated_activity.run_id
        if evidence_cache is not None and run_id in evidence_cache:
            evidence = evidence_cache[run_id]
        else:
            try:
                evidence = run_activity_port.evidence_for_run(run_id)
            except LookupError:
                evidence = None
            if evidence_cache is not None:
                evidence_cache[run_id] = evidence
        evidence_available = evidence is not None and bool(evidence.elapsed_s)
        if evidence is None:
            evidence = TrainingRunEvidence(
                summary=associated_activity,
                elapsed_s=[],
                distance_mi=[],
                heart_rate_bpm=[],
                run_walk_spans=[],
            )
        objective = evaluate_run_measurement(
            card=card,
            segments=segments,
            evidence=evidence,
        )
        if objective is not None:
            if not evidence_available:
                measurement = objective
            else:
                assessment_key = (run_id, occurrence_key, assessment_before)
                if measurement_assessment_port is None:
                    assessment = None
                elif assessment_cache is not None and assessment_key in assessment_cache:
                    assessment = assessment_cache[assessment_key]
                else:
                    assessment = measurement_assessment_port.latest_for(
                        run_id=run_id,
                        occurrence_key=occurrence_key,
                        before=assessment_before,
                    )
                    if assessment_cache is not None:
                        assessment_cache[assessment_key] = assessment
                required_measurement = next(
                    (
                        event.required
                        for event in block.measurement_events
                        if event.id == measurement_event_id
                    ),
                    False,
                )
                measurement = finalize_measurement(
                    objective,
                    assessment,
                    required_measurement,
                )

    return TrainingTodayCard(
        occurrence_key=occurrence_key,
        date=date,
        day=entry.day,
        slot=entry.slot,
        bundle_id=entry.bundle_id,
        bundle_name=bundle_names.get(entry.bundle_id, entry.bundle_id),
        is_running=is_running_bundle(entry.bundle_id),
        card=card,
        key_session=assignment.key_session,
        variants=assignment.variants,
        rule_display=render_rule(assignment.selection),
        gate_display=gate_display,
        variant_options=(
            [variant.id for variant in assignment.variants] if len(assignment.variants) >= 2 else []
        ),
        segments_display=segments_display,
        exercises_display=exercises_display,
        checkin_rows=rows,
        capture_rpe=capture_rpe,
        est_duration_min=card.est_duration_min,
        status=execution.status,
        execution=execution,
        variant_taken=log.variant_taken if log else None,
        notes=log.notes if log else None,
        capture=log.capture if log else None,
        associated_activity=associated_activity,
        run_candidates=run_candidates,
        measurement=measurement,
        measurement_event_id=measurement_event_id,
        measurement_attempt=measurement_attempt,
    )


def _card_sort_key(card: TrainingTodayCard) -> tuple[int, int, str]:
    """Sort key within one day: slot order, then check-in cards first, then card id.

    Block0 never schedules two check-in cards in the same slot, so the
    checkin-first tie-break only ever matters for `sup.daily` sharing the
    morning slot with a running card — this keeps the daily check-in visually
    first regardless of the bundles' own assignment order.
    """
    return (SLOT_HOUR.get(card.slot, 99), 0 if card.checkin_rows else 1, card.card.id)


def _measurement_attempt_metadata(
    entry: CompiledEntry,
    *,
    block: V3Block,
    activated_event_id: str | None,
) -> tuple[str | None, Literal["scheduled", "backup"] | None]:
    """Identify only authored scheduled attempts and activated backup copies."""
    if activated_event_id is not None:
        return activated_event_id, "backup"
    scheduled = [
        event
        for event in block.measurement_events
        if event.scheduled_day == entry.day and event.card_id == entry.card.id
    ]
    if len(scheduled) == 1:
        return scheduled[0].id, "scheduled"
    return None, None


def _occurrence_keys_for_entries(
    entries: list[tuple[int, CompiledEntry]],
    *,
    activation_by_index: dict[int, str],
) -> dict[int, str]:
    base_keys = {
        index: f"{entry.bundle_id}:{entry.card.id}:d{entry.day:02d}"
        for index, entry in entries
    }
    return {
        index: (
            f"{base_key}:event:{activation_by_index[index]}"
            if index in activation_by_index
            else base_key
        )
        for index, base_key in base_keys.items()
    }


def _cards_for_day(
    schedule: list[CompiledEntry],
    day: int,
    *,
    date: str,
    registry: SignalRegistry,
    library: ExerciseLibrary,
    bundle_names: dict[str, str],
    block: V3Block,
    repo: TrainingRepository,
    prior_logs: list[TrainingCardLog] | None = None,
    runs_today: list[TrainingRunActivitySummary] | None = None,
    run_activity_port: RunActivityReadPort | None = None,
    measurement_assessment_port: MeasurementAssessmentReadPort | None = None,
    backup_activations: tuple[MeasurementBackupActivation, ...] = (),
    assessment_before: str | None = None,
    evidence_cache: dict[str, TrainingRunEvidence | None] | None = None,
    assessment_cache: AssessmentCache | None = None,
) -> list[TrainingTodayCard]:
    """Build one day's cards, sorted for display.

    The caller bulk-loads run summaries, and every card shares this one date's
    list plus the day's run-card count. A linked measurement card may still
    read its own full evidence and exact assessment while being projected;
    request caches keep scheduling-state and visible projections on one
    evidence/assessment snapshot.
    """
    entries = [(index, entry) for index, entry in enumerate(schedule) if entry.day == day]
    run_cards_today = sum(
        1 for _index, entry in entries if is_running_bundle(entry.bundle_id)
    )
    day_runs = runs_today or []
    activation_by_index = {
        activation.entry_index: activation.event_id for activation in backup_activations
    }
    occurrence_keys = _occurrence_keys_for_entries(
        entries,
        activation_by_index=activation_by_index,
    )
    cards: list[TrainingTodayCard] = []
    for entry_index, entry in entries:
        event_id, attempt = _measurement_attempt_metadata(
            entry,
            block=block,
            activated_event_id=activation_by_index.get(entry_index),
        )
        cards.append(
            _build_card(
                entry,
                date=date,
                registry=registry,
                library=library,
                bundle_names=bundle_names,
                block=block,
                repo=repo,
                prior_logs=prior_logs,
                runs_today=day_runs,
                run_cards_today=run_cards_today,
                run_activity_port=run_activity_port,
                measurement_assessment_port=measurement_assessment_port,
                measurement_event_id=event_id,
                measurement_attempt=attempt,
                occurrence_key_override=occurrence_keys[entry_index],
                assessment_before=assessment_before,
                evidence_cache=evidence_cache,
                assessment_cache=assessment_cache,
            )
        )
    cards.sort(key=_card_sort_key)
    return cards


def _date_for_block_day(block: V3Block, day: int) -> str:
    start = date_cls.fromisoformat(block.window.start)
    return (start + timedelta(days=day - 1)).isoformat()


def _runs_grouped_by_date(
    summaries: list[TrainingRunActivitySummary],
) -> dict[str, list[TrainingRunActivitySummary]]:
    grouped: dict[str, list[TrainingRunActivitySummary]] = {}
    for summary in summaries:
        grouped.setdefault(summary.session_date, []).append(summary)
    return grouped


def _record_measurement_attempts(
    statuses: dict[str, dict[int, MeasurementStatus]],
    cards: list[TrainingTodayCard],
) -> None:
    for card in cards:
        if card.measurement_event_id is None or card.measurement_attempt is None:
            continue
        if card.measurement is None:
            continue
        statuses.setdefault(card.measurement_event_id, {})[card.day] = card.measurement.status


def _evaluate_resolved_measurement_attempts(
    *,
    resolutions: dict[int, MeasurementDayResolution],
    through_day: int,
    assessment_before: str | None,
    block: V3Block,
    registry: SignalRegistry,
    library: ExerciseLibrary,
    bundle_names: dict[str, str],
    repo: TrainingRepository,
    runs_by_date: dict[str, list[TrainingRunActivitySummary]],
    run_activity_port: RunActivityReadPort | None,
    measurement_assessment_port: MeasurementAssessmentReadPort | None,
    evidence_cache: dict[str, TrainingRunEvidence | None] | None = None,
    assessment_cache: AssessmentCache | None = None,
) -> dict[str, dict[int, MeasurementStatus]]:
    """Evaluate already-frozen active attempts through one block day."""
    statuses: dict[str, dict[int, MeasurementStatus]] = {}
    if run_activity_port is None:
        return statuses
    for attempt_day, resolution in sorted(resolutions.items()):
        if attempt_day > through_day:
            continue
        attempt_date = _date_for_block_day(block, attempt_day)
        cards = _cards_for_day(
            list(resolution.entries),
            attempt_day,
            date=attempt_date,
            registry=registry,
            library=library,
            bundle_names=bundle_names,
            block=block,
            repo=repo,
            runs_today=runs_by_date.get(attempt_date, []),
            run_activity_port=run_activity_port,
            measurement_assessment_port=measurement_assessment_port,
            backup_activations=resolution.activations,
            assessment_before=assessment_before,
            evidence_cache=evidence_cache,
            assessment_cache=assessment_cache,
        )
        _record_measurement_attempts(statuses, cards)
    return statuses


def _resolve_measurement_history(
    *,
    through_day: int,
    block: V3Block,
    schedule: list[CompiledEntry],
    registry: SignalRegistry,
    library: ExerciseLibrary,
    bundle_names: dict[str, str],
    repo: TrainingRepository,
    runs_by_date: dict[str, list[TrainingRunActivitySummary]],
    run_activity_port: RunActivityReadPort | None,
    measurement_assessment_port: MeasurementAssessmentReadPort | None,
    evidence_cache: dict[str, TrainingRunEvidence | None],
    assessment_cache: AssessmentCache,
) -> dict[int, MeasurementDayResolution]:
    """Freeze each authored opportunity using evidence available before that day."""
    resolutions: dict[int, MeasurementDayResolution] = {}
    attempt_days = sorted(
        {
            attempt_day
            for event in block.measurement_events
            for attempt_day in (event.scheduled_day, *event.backup_days)
            if attempt_day <= through_day
        }
    )
    # Each opportunity needs prior attempts re-evaluated at its own cutoff.
    # Imported blocks are small, and request caches prevent identical reads.
    for attempt_day in attempt_days:
        prior_statuses = _evaluate_resolved_measurement_attempts(
            resolutions=resolutions,
            through_day=attempt_day - 1,
            assessment_before=_date_for_block_day(block, attempt_day),
            block=block,
            registry=registry,
            library=library,
            bundle_names=bundle_names,
            repo=repo,
            runs_by_date=runs_by_date,
            run_activity_port=run_activity_port,
            measurement_assessment_port=measurement_assessment_port,
            evidence_cache=evidence_cache,
            assessment_cache=assessment_cache,
        )
        resolutions[attempt_day] = resolve_measurement_day(
            block=block,
            schedule=schedule,
            day=attempt_day,
            attempt_statuses=prior_statuses,
        )
    return resolutions


def _summary_horizon_start(block: V3Block, requested_start: str, before_day: int) -> str:
    prior_scheduled_days = [
        event.scheduled_day
        for event in block.measurement_events
        if event.scheduled_day < before_day
    ]
    if not prior_scheduled_days:
        return requested_start
    earliest_attempt = _date_for_block_day(block, min(prior_scheduled_days))
    return min(requested_start, earliest_attempt)


def _summary_horizon_end(block: V3Block, requested_end: str, as_of_day: int) -> str:
    elapsed_attempt_days = [
        attempt_day
        for event in block.measurement_events
        for attempt_day in (event.scheduled_day, *event.backup_days)
        if attempt_day <= as_of_day
    ]
    if not elapsed_attempt_days:
        return requested_end
    latest_attempt = _date_for_block_day(block, max(elapsed_attempt_days))
    return max(requested_end, latest_attempt)


# ---------- public read models ----------


def get_training_today(
    repo: TrainingRepository,
    *,
    date: str,
    run_activity_port: RunActivityReadPort | None = None,
    measurement_assessment_port: MeasurementAssessmentReadPort | None = None,
) -> TrainingTodayResponse:
    """Return one day's compiled schedule enriched with any saved capture logs.

    `day` is None either when nothing is imported yet or when `date` falls
    outside the active block's window; `block_id`/`block_name` stay populated
    in the latter case so a caller can distinguish "no block imported" from
    "block active, but not scheduled for this date" (before it starts or
    after it ends).

    `run_activity_port` drives run<->prescription association and is optional
    so callers that do not need tracked-run enrichment do not need a fake.
    """
    context = _active_context(repo)
    if context is None:
        return TrainingTodayResponse(date=date, cards=[])
    block, bundles, registry, library = context
    day = _day_number(block, date)
    if not 1 <= day <= block.window.days:
        return TrainingTodayResponse(
            date=date, block_id=block.id, block_name=block.id, day=None, cards=[]
        )

    bundle_names = {bundle.id: bundle.name for bundle in bundles}
    schedule = compile_schedule(bundles)
    prior_logs = repo.card_logs_before(date)
    summary_start = _summary_horizon_start(block, date, day)
    run_summaries = (
        run_activity_port.runs_between(summary_start, date) if run_activity_port is not None else []
    )
    runs_by_date = _runs_grouped_by_date(run_summaries)
    evidence_cache: dict[str, TrainingRunEvidence | None] = {}
    assessment_cache: AssessmentCache = {}
    resolutions = _resolve_measurement_history(
        through_day=day,
        block=block,
        schedule=schedule,
        registry=registry,
        library=library,
        bundle_names=bundle_names,
        repo=repo,
        runs_by_date=runs_by_date,
        run_activity_port=run_activity_port,
        measurement_assessment_port=measurement_assessment_port,
        evidence_cache=evidence_cache,
        assessment_cache=assessment_cache,
    )
    resolution = resolutions.get(day)
    if resolution is None:
        resolution = resolve_measurement_day(
            block=block,
            schedule=schedule,
            day=day,
            attempt_statuses={},
        )
    cards = _cards_for_day(
        list(resolution.entries),
        day,
        date=date,
        registry=registry,
        library=library,
        block=block,
        bundle_names=bundle_names,
        repo=repo,
        prior_logs=prior_logs,
        runs_today=runs_by_date.get(date, []),
        run_activity_port=run_activity_port,
        measurement_assessment_port=measurement_assessment_port,
        backup_activations=resolution.activations,
        evidence_cache=evidence_cache,
        assessment_cache=assessment_cache,
    )
    return TrainingTodayResponse(
        date=date, block_id=block.id, block_name=block.id, day=day, cards=cards
    )


def get_training_schedule_window(
    repo: TrainingRepository,
    *,
    start_date: str,
    duration_days: int = 14,
    run_activity_port: RunActivityReadPort | None = None,
    measurement_assessment_port: MeasurementAssessmentReadPort | None = None,
    as_of_date: str | None = None,
) -> TrainingScheduleWindow:
    """Return a multi-day schedule projection starting at `start_date`.

    Every calendar day in the window gets a `TrainingScheduleDay` — `day` is
    always the raw block-day offset (which may be outside `[1, window.days]`
    or, with no active block, meaningless), and `cards` is simply empty for
    out-of-window days rather than the day being omitted. This keeps the
    window a fixed-length calendar strip a caller can lay out without gaps.
    `required_actions` reflects elapsed program state as of `as_of_date`
    (local today by default), never the visible window's end date.
    """
    start = date_cls.fromisoformat(start_date)
    end = start + timedelta(days=duration_days - 1)
    context = _active_context(repo)
    if context is None:
        return TrainingScheduleWindow(start_date=start_date, end_date=end.isoformat(), days=[])

    block, bundles, registry, library = context
    bundle_names = {bundle.id: bundle.name for bundle in bundles}
    schedule = compile_schedule(bundles)
    effective_as_of = as_of_date or date_cls.today().isoformat()
    as_of_day = _day_number(block, effective_as_of)
    summary_start = _summary_horizon_start(
        block,
        start_date,
        as_of_day + 1,
    )
    summary_end = _summary_horizon_end(block, end.isoformat(), as_of_day)
    run_summaries = (
        run_activity_port.runs_between(summary_start, summary_end)
        if run_activity_port is not None
        else []
    )
    runs_by_date = _runs_grouped_by_date(run_summaries)
    evidence_cache: dict[str, TrainingRunEvidence | None] = {}
    assessment_cache: AssessmentCache = {}
    visible_end_day = _day_number(block, end.isoformat())
    resolutions = _resolve_measurement_history(
        through_day=max(as_of_day, visible_end_day),
        block=block,
        schedule=schedule,
        registry=registry,
        library=library,
        bundle_names=bundle_names,
        repo=repo,
        runs_by_date=runs_by_date,
        run_activity_port=run_activity_port,
        measurement_assessment_port=measurement_assessment_port,
        evidence_cache=evidence_cache,
        assessment_cache=assessment_cache,
    )
    current_statuses = _evaluate_resolved_measurement_attempts(
        resolutions=resolutions,
        through_day=as_of_day,
        assessment_before=_date_for_block_day(block, as_of_day + 1),
        block=block,
        registry=registry,
        library=library,
        bundle_names=bundle_names,
        repo=repo,
        runs_by_date=runs_by_date,
        run_activity_port=run_activity_port,
        measurement_assessment_port=measurement_assessment_port,
        evidence_cache=evidence_cache,
        assessment_cache=assessment_cache,
    )
    action_resolution = resolve_measurement_day(
        block=block,
        schedule=schedule,
        day=as_of_day,
        attempt_statuses=current_statuses,
    )

    days: list[TrainingScheduleDay] = []
    for offset in range(duration_days):
        current = start + timedelta(days=offset)
        current_iso = current.isoformat()
        day_number = _day_number(block, current_iso)
        resolution = resolutions.get(day_number)
        if resolution is None:
            resolution = resolve_measurement_day(
                block=block,
                schedule=schedule,
                day=day_number,
                attempt_statuses=current_statuses,
            )
        cards = (
            _cards_for_day(
                list(resolution.entries),
                day_number,
                date=current_iso,
                registry=registry,
                library=library,
                block=block,
                bundle_names=bundle_names,
                repo=repo,
                runs_today=runs_by_date.get(current_iso, []),
                run_activity_port=run_activity_port,
                measurement_assessment_port=measurement_assessment_port,
                backup_activations=resolution.activations,
                evidence_cache=evidence_cache,
                assessment_cache=assessment_cache,
            )
            if 1 <= day_number <= block.window.days
            else []
        )
        days.append(TrainingScheduleDay(date=current_iso, day=day_number, cards=cards))

    return TrainingScheduleWindow(
        start_date=start_date,
        end_date=end.isoformat(),
        days=days,
        required_actions=list(action_resolution.required_actions),
    )


def get_block_status(repo: TrainingRepository) -> TrainingBlockStatus | None:
    """Return the active block's lifecycle snapshot, or None if nothing is imported.

    `current_day`/`burn_in` are relative to the real calendar date
    (`date.today()`), not any caller-supplied date — this is a block-level
    status view, not a per-day schedule projection. Both are None when today
    falls outside the block's window.
    """
    stored_block = repo.active_block()
    if stored_block is None:
        return None
    block = V3Block.model_validate(stored_block.artifact)
    today = date_cls.today().isoformat()
    day = _day_number(block, today)
    in_window = 1 <= day <= block.window.days
    return TrainingBlockStatus(
        block=block,
        lint_report=stored_block.lint_report,
        warning_acks=list(stored_block.warning_acks),
        current_day=day if in_window else None,
        burn_in=(week_of(day) == 1) if in_window else None,
        activated_at=stored_block.activated_at,
    )


class TrainingLogUpdateRequest(StrictDefaultsRequired):
    """Partial update for one card occurrence's capture log.

    Every field is optional, and presence — not nullness — decides what
    happens: a field the request body omits keeps the existing log's value,
    while a field the body includes is applied verbatim, even when its value
    is explicit `null`. For `notes`/`variant_taken`/`capture`/`linked_run_id`
    an explicit `null` clears the stored value. `status`/`run_link_detached`
    have no defined "cleared" state (a stored log's `status` always has a
    concrete value, defaulting to `"pending"`; `run_link_detached` is always
    a concrete bool, defaulting to `False`), so callers are expected to only
    ever send them as a real literal — an explicit `null` is treated the
    same as the field being absent; see `upsert_training_log` for how
    presence is resolved via `model_fields_set`. Both are typed `X | None`
    (rather than a bare, always-required `bool`/literal) purely so the field
    stays optional to omit in the generated OpenAPI/TypeScript request type.

    `linked_run_id`/`run_link_detached` are the run-card association
    controls: setting `linked_run_id` manually links one of the date's
    tracked runs (validated against the runtime-resolved card's candidates —
    a non-null id absent from that date's runs raises `ValueError`, mapped
    to 400 by the app-level exception handler); setting `run_link_detached`
    (with no `linked_run_id` in the same request) suppresses auto-matching
    for this occurrence without picking a specific run. See
    `match_run_to_card` for how the two combine when both are stored.
    """

    status: TrainingCardStatus | None = None
    variant_taken: str | None = None
    notes: str | None = None
    capture: TrainingCaptureLog | None = None
    linked_run_id: str | None = None
    run_link_detached: bool | None = None


def _resolve_occurrence_or_raise(
    repo: TrainingRepository,
    *,
    date: str,
    occurrence_key: str,
    run_activity_port: RunActivityReadPort | None,
    measurement_assessment_port: MeasurementAssessmentReadPort | None,
) -> TrainingTodayCard:
    """Return the runtime-resolved card or raise `LookupError`.

    Validation deliberately uses the same Today overlay and injected evidence
    ports as the read path. That admits an activated authored backup while
    rejecting the same opaque key when a valid prior result leaves the backup
    inactive; raw compiled keys alone cannot represent that distinction.
    """
    response = get_training_today(
        repo,
        date=date,
        run_activity_port=run_activity_port,
        measurement_assessment_port=measurement_assessment_port,
    )
    match = next((card for card in response.cards if card.occurrence_key == occurrence_key), None)
    if match is not None:
        return match
    raise LookupError(f"no scheduled occurrence {occurrence_key} on {date}")


def upsert_training_log(
    repo: TrainingRepository,
    *,
    date: str,
    occurrence_key: str,
    update: TrainingLogUpdateRequest,
    run_activity_port: RunActivityReadPort | None = None,
    measurement_assessment_port: MeasurementAssessmentReadPort | None = None,
) -> TrainingCardLog:
    """Apply a partial update to one card occurrence's capture log and persist it.

    Raises `LookupError` (404 at the route layer) when `occurrence_key` is
    not a card displayed by the active block's runtime Today overlay for
    `date` — see `_resolve_occurrence_or_raise`. Fields absent
    from `update.model_fields_set` keep the existing log's value; fields
    present are applied as-is, including an explicit `None` clearing
    `notes`/`variant_taken`/`capture`/`linked_run_id`. `status` is the one
    exception: a stored log's `status` has no `None` state
    (`TrainingCardLog.status` is never optional), so an explicit
    `status: null` is treated the same as `status` being absent rather than
    being forwarded — there is nothing valid to clear it to. A first-time
    update against an occurrence with no prior log starts every absent field
    at its `TrainingCardLog` default (`status="pending"`, the rest `None`/
    `False`). Calling this twice with an identical `update` is idempotent:
    the second call persists the same values the first one wrote.

    Raises `ValueError` (400 at the route layer) when the request sets a
    non-null `linked_run_id` that isn't among `run_activity_port`'s runs for
    `date` — this is write-time validation, distinct from
    `match_run_to_card`'s read-time tolerance for a link that was valid when
    saved but has since gone stale (e.g. a re-ingest changed run ids); a
    missing `run_activity_port` is treated the same as "no runs for this
    date" (any non-null `linked_run_id` is rejected).
    """
    resolved_card = _resolve_occurrence_or_raise(
        repo,
        date=date,
        occurrence_key=occurrence_key,
        run_activity_port=run_activity_port,
        measurement_assessment_port=measurement_assessment_port,
    )
    existing = repo.card_log(date, occurrence_key)
    fields_set = update.model_fields_set
    status = (
        update.status
        if "status" in fields_set and update.status is not None
        else (existing.status if existing else "pending")
    )
    variant_taken = (
        update.variant_taken
        if "variant_taken" in fields_set
        else (existing.variant_taken if existing else None)
    )
    notes = update.notes if "notes" in fields_set else (existing.notes if existing else None)
    capture = (
        update.capture if "capture" in fields_set else (existing.capture if existing else None)
    )
    linked_run_id = (
        update.linked_run_id
        if "linked_run_id" in fields_set
        else (existing.linked_run_id if existing else None)
    )
    run_link_detached = (
        update.run_link_detached
        if "run_link_detached" in fields_set and update.run_link_detached is not None
        else (existing.run_link_detached if existing else False)
    )
    if (
        "linked_run_id" in fields_set
        and update.linked_run_id is not None
        and not any(
            run.run_id == update.linked_run_id for run in resolved_card.run_candidates
        )
    ):
        raise ValueError(f"run {update.linked_run_id!r} is not a tracked run for {date}")
    log = TrainingCardLog(
        id=f"{date}:{occurrence_key}",
        date=date,
        occurrence_key=occurrence_key,
        status=status,
        variant_taken=variant_taken,
        notes=notes,
        capture=capture,
        linked_run_id=linked_run_id,
        run_link_detached=run_link_detached,
    )
    repo.upsert_card_log(log)
    return log


__all__ = [
    "TrainingLogUpdateRequest",
    "build_exercise_display",
    "build_segment_display",
    "checkin_rows",
    "get_block_status",
    "get_training_schedule_window",
    "get_training_today",
    "last_logged_for",
    "match_run_to_card",
    "render_gate",
    "render_rule",
    "render_scheme",
    "render_segment",
    "structured_load",
    "upsert_training_log",
]
