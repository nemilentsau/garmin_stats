"""Today/schedule-window/block-status read models plus capture-log upsert.

Owns the projection from Task 1's typed v3 wire contracts (`V3Block`,
`V3Bundle`, `V3Card`, ...) and Task 2's compiled schedule (`compile_schedule`,
`full_variant_prescription`) into the display-ready `Training*` view models
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

`upsert_training_log` applies a partial update keyed off
`TrainingLogUpdateRequest.model_fields_set`: a field the caller omitted from
the request body keeps the existing log's value, while a field the caller
included — even as an explicit `null` — is applied, clearing it when the
value is `None`. This is "PATCH" semantics, not a mirror of the routines
Today board (that backend always full-replaces a card log on save); it also
rejects capture PUTs against an occurrence the compiled schedule doesn't
recognize for the given date, raising `LookupError` (mapped to 404 by the
app-level exception handler) rather than persisting a log nothing will ever
display.
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
    week_of,
)
from app.domains.training.contracts import (
    AllPredicate,
    AnyPredicate,
    Cmp,
    ExerciseLibrary,
    ExercisePrescriptionSpec,
    LoadSpec,
    MeasurementContract,
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
    TrainingExerciseDisplay,
    TrainingLastLogged,
    TrainingScheduleDay,
    TrainingScheduleWindow,
    TrainingSegmentDisplay,
    TrainingTodayCard,
    TrainingTodayResponse,
    V3Block,
    V3Bundle,
)
from app.domains.training.dependencies import TrainingRepository

# ---------- signal short-names + predicate/render helpers ----------

_SIGNAL_LABELS: dict[str, str] = {
    "hrv.dev_swc": "HRV (SWC units)",
    "rhr.delta_7d": "RHR delta (bpm)",
    "sleep.score": "sleep score",
    "env.dew_point": "dew point (°C)",
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
        value_display = _num(value)
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

    `scheme` (via `render_scheme`) stays alongside the new structured
    `reps_low`/`reps_high`/`load_kind`/`load_value` fields for this phase's
    back-compat; `last` is always the caller's value verbatim — this task
    never looks one up (Task 0.3's `last_logged_for` does).
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


def _build_card(
    entry: CompiledEntry,
    *,
    date: str,
    registry: SignalRegistry,
    library: ExerciseLibrary,
    bundle_names: dict[str, str],
    repo: TrainingRepository,
) -> TrainingTodayCard:
    """Project one compiled schedule entry into a display-ready Today card, log merged in."""
    card = entry.card
    assignment = entry.assignment
    occurrence_key = f"{entry.bundle_id}:{card.id}:d{entry.day:02d}"

    segments_display: list[TrainingSegmentDisplay] = []
    exercises_display: list[TrainingExerciseDisplay] = []
    log_sets = any(field.type == "set_rep_load[]" for field in card.capture)
    if isinstance(card.prescription, StrengthPrescription):
        exercises_display = [
            build_exercise_display(
                exercise,
                name=_exercise_name(library, exercise.exercise_id),
                log_sets=log_sets,
                last=None,
            )
            for exercise in card.prescription.exercises
        ]
    else:
        patched = full_variant_prescription(entry)
        segments_display = [
            TrainingSegmentDisplay(label=segment.label, detail=render_segment(segment))
            for segment in (
                SegmentSpec.model_validate(raw) for raw in patched.get("segments", [])
            )
        ]

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

    return TrainingTodayCard(
        occurrence_key=occurrence_key,
        date=date,
        day=entry.day,
        slot=entry.slot,
        bundle_id=entry.bundle_id,
        bundle_name=bundle_names.get(entry.bundle_id, entry.bundle_id),
        card=card,
        key_session=assignment.key_session,
        variants=assignment.variants,
        rule_display=render_rule(assignment.selection),
        gate_display=gate_display,
        variant_options=(
            [variant.id for variant in assignment.variants]
            if len(assignment.variants) >= 2
            else []
        ),
        segments_display=segments_display,
        exercises_display=exercises_display,
        checkin_rows=rows,
        capture_rpe=capture_rpe,
        est_duration_min=card.est_duration_min,
        status=log.status if log else "pending",
        variant_taken=log.variant_taken if log else None,
        notes=log.notes if log else None,
        capture=log.capture if log else None,
    )


def _card_sort_key(card: TrainingTodayCard) -> tuple[int, int, str]:
    """Sort key within one day: slot order, then check-in cards first, then card id.

    Block0 never schedules two check-in cards in the same slot, so the
    checkin-first tie-break only ever matters for `sup.daily` sharing the
    morning slot with a running card — this keeps the daily check-in visually
    first regardless of the bundles' own assignment order.
    """
    return (SLOT_HOUR.get(card.slot, 99), 0 if card.checkin_rows else 1, card.card.id)


def _cards_for_day(
    schedule: list[CompiledEntry],
    day: int,
    *,
    date: str,
    registry: SignalRegistry,
    library: ExerciseLibrary,
    bundle_names: dict[str, str],
    repo: TrainingRepository,
) -> list[TrainingTodayCard]:
    entries = [entry for entry in schedule if entry.day == day]
    cards = [
        _build_card(
            entry, date=date, registry=registry, library=library, bundle_names=bundle_names,
            repo=repo,
        )
        for entry in entries
    ]
    cards.sort(key=_card_sort_key)
    return cards


# ---------- public read models ----------


def get_training_today(repo: TrainingRepository, *, date: str) -> TrainingTodayResponse:
    """Return one day's compiled schedule enriched with any saved capture logs.

    `day` is None either when nothing is imported yet or when `date` falls
    outside the active block's window; `block_id`/`block_name` stay populated
    in the latter case so a caller can distinguish "no block imported" from
    "block active, but not scheduled for this date" (before it starts or
    after it ends).
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
    cards = _cards_for_day(
        schedule, day, date=date, registry=registry, library=library,
        bundle_names=bundle_names, repo=repo,
    )
    return TrainingTodayResponse(
        date=date, block_id=block.id, block_name=block.id, day=day, cards=cards
    )


def get_training_schedule_window(
    repo: TrainingRepository, *, start_date: str, duration_days: int = 14
) -> TrainingScheduleWindow:
    """Return a multi-day schedule projection starting at `start_date`.

    Every calendar day in the window gets a `TrainingScheduleDay` — `day` is
    always the raw block-day offset (which may be outside `[1, window.days]`
    or, with no active block, meaningless), and `cards` is simply empty for
    out-of-window days rather than the day being omitted. This keeps the
    window a fixed-length calendar strip a caller can lay out without gaps.
    """
    start = date_cls.fromisoformat(start_date)
    end = start + timedelta(days=duration_days - 1)
    context = _active_context(repo)
    if context is None:
        return TrainingScheduleWindow(start_date=start_date, end_date=end.isoformat(), days=[])

    block, bundles, registry, library = context
    bundle_names = {bundle.id: bundle.name for bundle in bundles}
    schedule = compile_schedule(bundles)

    days: list[TrainingScheduleDay] = []
    for offset in range(duration_days):
        current = start + timedelta(days=offset)
        current_iso = current.isoformat()
        day_number = _day_number(block, current_iso)
        cards = (
            _cards_for_day(
                schedule, day_number, date=current_iso, registry=registry, library=library,
                bundle_names=bundle_names, repo=repo,
            )
            if 1 <= day_number <= block.window.days
            else []
        )
        days.append(TrainingScheduleDay(date=current_iso, day=day_number, cards=cards))

    return TrainingScheduleWindow(start_date=start_date, end_date=end.isoformat(), days=days)


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
    is explicit `null`. For `notes`/`variant_taken`/`capture` an explicit
    `null` clears the stored value. `status` has no defined "cleared" state
    (a stored log's `status` always has a concrete value, defaulting to
    `"pending"`), so callers are expected to only ever send it as a real
    status literal; see `upsert_training_log` for how presence is resolved
    via `model_fields_set`.
    """

    status: TrainingCardStatus | None = None
    variant_taken: str | None = None
    notes: str | None = None
    capture: TrainingCaptureLog | None = None


def _resolve_occurrence_or_raise(
    repo: TrainingRepository, *, date: str, occurrence_key: str
) -> None:
    """Raise `LookupError` unless `occurrence_key` is really scheduled on `date`.

    Reuses `get_training_today`'s own resolution path — active block, day
    number, compiled schedule — rather than trusting the caller-supplied
    key: `date` outside the active block's window, or an `occurrence_key`
    that doesn't match any compiled entry for that day (including "no
    active block at all"), both 404 rather than silently persisting a log
    no Today/schedule view will ever surface.
    """
    context = _active_context(repo)
    if context is not None:
        block, bundles, _registry, _library = context
        day = _day_number(block, date)
        if 1 <= day <= block.window.days:
            schedule = compile_schedule(bundles)
            known_keys = {
                f"{entry.bundle_id}:{entry.card.id}:d{entry.day:02d}"
                for entry in schedule
                if entry.day == day
            }
            if occurrence_key in known_keys:
                return
    raise LookupError(f"no scheduled occurrence {occurrence_key} on {date}")


def upsert_training_log(
    repo: TrainingRepository, *, date: str, occurrence_key: str, update: TrainingLogUpdateRequest
) -> TrainingCardLog:
    """Apply a partial update to one card occurrence's capture log and persist it.

    Raises `LookupError` (404 at the route layer) when `occurrence_key` is
    not a real scheduled occurrence for `date` under the active block's
    compiled schedule — see `_resolve_occurrence_or_raise`. Fields absent
    from `update.model_fields_set` keep the existing log's value; fields
    present are applied as-is, including an explicit `None` clearing
    `notes`/`variant_taken`/`capture`. `status` is the one exception: a
    stored log's `status` has no `None` state (`TrainingCardLog.status` is
    never optional), so an explicit `status: null` is treated the same as
    `status` being absent rather than being forwarded — there is nothing
    valid to clear it to. A first-time update against an occurrence with no
    prior log starts every absent field at its `TrainingCardLog` default
    (`status="pending"`, the rest `None`). Calling this twice with an
    identical `update` is idempotent: the second call persists the same
    values the first one wrote.
    """
    _resolve_occurrence_or_raise(repo, date=date, occurrence_key=occurrence_key)
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
    log = TrainingCardLog(
        id=f"{date}:{occurrence_key}",
        date=date,
        occurrence_key=occurrence_key,
        status=status,
        variant_taken=variant_taken,
        notes=notes,
        capture=capture,
    )
    repo.upsert_card_log(log)
    return log


__all__ = [
    "TrainingLogUpdateRequest",
    "build_exercise_display",
    "checkin_rows",
    "get_block_status",
    "get_training_schedule_window",
    "get_training_today",
    "render_gate",
    "render_rule",
    "render_scheme",
    "render_segment",
    "structured_load",
    "upsert_training_log",
]
