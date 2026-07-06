# Bundle-Specific Cards — Design

**Date:** 2026-06-29
**Branch:** `bundles-cards`
**Status:** Approved design, pending implementation plan

## Problem

Routine cards today have a single `renderer` field (`timer_session` / `checklist_block` /
`exercise_block`) — an *interaction primitive*. The frontend switches layout purely on
`renderer`, giving one generic layout per renderer. There is no notion of *what activity a
card is for*.

This conflation breaks down as the bundle library grows. `renderer` and activity domain are
genuinely orthogonal:

| Domain | Workout cards (today's renderer) | Support cards |
|--------|----------------------------------|---------------|
| Running | `exercise_block` × 7 + LTHR test | `checklist_block` (weekly review, HR strap setup) |
| Strength | `exercise_block` × 6 (push/pull/lower A/B) | `checklist_block` (skip day, weekly review) |
| Breathwork | `timer_session` × 8 (resonance/exhale/box/CO2) | `checklist_block` (weekly review) |
| Meditation | `timer_session` × 3 (focused/open) | `checklist_block` (weekly review) |

`exercise_block` is shared by running *and* strength; `timer_session` by breathwork *and*
meditation. A generic exercise list cannot properly express a *running workout* (pace, HR zone,
talk test) the way it cannot express a *strength session* (sets × reps × load × RIR) — even
though both are `exercise_block` today. Structured data is currently buried in text: running
encodes "Workout type / RPE / Talk test / HR guidance" inside an instructions blob; strength
fakes a `post_session_ratings` row as a fake exercise; breath/meditation already carry proper
`rating_prompts`.

These bundles (strength, running, breathwork, meditation) are first-class and will keep being
used. They each merit dedicated cards across three dimensions: **data shape**, **presentation**,
and **logging**.

## Goals

- First-class per-domain card types with typed payloads, dedicated frontend components, and
  per-domain logging.
- Type information flows properly through the contract → OpenAPI → `api-types.ts` pipeline, so
  the frontend gets a real discriminated union (zero hand-written types).
- Full per-unit logging (per-set strength, per-run actuals, rating prompts, checklist answers).
- Per-domain visual identity (accent + icon).
- Both surfaces — the Today board and the schedule detail panel — render the new components.

## Non-Goals

- No backward-compatible legacy `renderer` path. Bundles are re-authored and re-imported; old
  imported card data is disposable.
- No unrelated refactoring of the routines/artifacts domains beyond what the discriminator
  change requires.

## Decisions (from brainstorming)

1. **Axis** — cards key on *activity domain*, not per-bundle. Bundles compose domain cards.
2. **Type model** — a single discriminated union, not two orthogonal axes. Workout cards get
   rich domain types; reviews/setup/skip stay as ONE shared `checklist` type, themed by domain.
3. **Migration** — re-author the 6 bundle JSONs to the typed schema and re-import. Treat
   existing imported cards as disposable.
4. **Logging** — full per-unit actuals.
5. **Surfaces** — Today board *and* schedule detail panel.
6. **Theming** — per-domain accent + icon (ux-design pass), demoting slot accents to secondary.

## Backend Data Model

### Discriminator

Replace `renderer` with a `card_type` discriminator across the contracts:

```python
CardType = Literal[
    "running_workout", "strength_session", "breath_timer", "meditation_timer", "checklist"
]
```

`payload_json: dict[str, object]` and `actual_json: dict[str, object]` become **typed
discriminated unions** keyed on `card_type` via Pydantic `Field(discriminator="card_type")`, so
OpenAPI emits a tagged union and `api-types.ts` is fully typed.

**Contracts touched** (`renderer` removed everywhere):
- `backend/app/domains/routines/contracts.py`: `CardTemplate`, `ScheduleOccurrence`,
  `TodayCard`, `CardLog`, `TodayCardLogUpdateRequest`.
- `backend/app/domains/artifacts/contracts.py`: `CardTemplateSpec` (and any `RendererFamily`
  references).

### Typed payloads

Shared:

```python
class RatingPrompt:
    key: str
    label: str
    scale_min: int = 1
    scale_max: int = 5
```

```python
class RunningWorkoutPayload:
    card_type: Literal["running_workout"]
    workout_type: str            # easy, recovery, long_easy, easy_plus_strides, steady, progression, lthr_test
    rpe: str | None
    talk_test: str | None
    hr_guidance: str | None
    calibration_quality: bool    # chest-strap requirement (today a sentence in instructions)
    instructions: str | None
    segments: list[RunSegment]

class RunSegment:
    id: str
    label: str
    kind: Literal["warmup", "main", "strides", "cooldown", "intervals"]
    detail: str | None
    prescription: str            # flexible range string, e.g. "35-50 min", "4-8 x 15-20s"
```

```python
class StrengthSessionPayload:
    card_type: Literal["strength_session"]
    session_focus: str | None    # "Chest + Side Delts"
    duration_minutes: int | None
    rir_guidance: str | None     # "1-3 reps in reserve"
    instructions: str | None
    exercises: list[StrengthExercise]
    rating_prompts: list[RatingPrompt]   # promoted out of the fake post_session_ratings row

class StrengthExercise:
    id: str
    label: str
    detail: str | None
    set_scheme: str              # "3x5-8" (sets x rep-range), prescription as a string
```

```python
class BreathTimerPayload:
    card_type: Literal["breath_timer"]
    duration_minutes: int
    pattern_label: str           # "4s in / 4s hold / 4s out / 4s hold"
    phases: list[BreathPhase]    # enables the breathing animation
    instructions: str | None
    rating_prompts: list[RatingPrompt]

class BreathPhase:
    kind: Literal["inhale", "hold_full", "exhale", "hold_empty"]
    seconds: int
```

```python
class MeditationTimerPayload:
    card_type: Literal["meditation_timer"]
    duration_minutes: int
    technique: str               # focused_attention / open_monitoring
    anchor: str | None           # "exhale count"
    instructions: str | None
    rating_prompts: list[RatingPrompt]
```

```python
class ChecklistPayload:
    card_type: Literal["checklist"]
    instructions: str | None
    items: list[ChecklistItem]
    domain: str | None           # running/strength/breathwork/meditation, for theming

class ChecklistItem:
    id: str
    label: str
    detail: str | None
```

**Prescription strings are intentional.** Running segment prescriptions ("35-50 min") and
strength `set_scheme` ("3x5-8") are *ranges*, not exact values. They stay strings on the
prescription side; the *log* side records exact numbers (see below). That asymmetry is the
point: prescription is a target range, the log is what actually happened.

### Typed log / actual schemas (full per-unit)

```python
class RunningActual:
    card_type: Literal["running_workout"]
    distance_km: float | None
    duration_min: float | None
    avg_hr: int | None
    hr_drift_pct: float | None
    calibration_quality: bool    # did you actually use the strap?
    rpe: int | None
    notes: str | None
```

```python
class StrengthActual:
    card_type: Literal["strength_session"]
    exercises: list[LoggedStrengthExercise]
    ratings: dict[str, int]      # keyed by rating_prompt.key

class LoggedStrengthExercise:
    exercise_id: str | None      # links a prescribed exercise; None for extras
    label: str | None            # display name; required when is_extra (free text)
    is_extra: bool = False       # persisted flag marking off-script work in the DB
    sets: list[StrengthSetLog]

class StrengthSetLog:
    set_index: int
    weight: float | None
    reps: int | None
    rir: int | None
```

Extras: an off-script exercise done on a given day is logged as a `LoggedStrengthExercise`
with `exercise_id = None`, a free-text `label`, and `is_extra = True`. That flag lands in
`actual_json` so extras are distinguishable/queryable from prescribed work. Nesting sets under
exercises makes both prescribed and extra logging natural.

```python
class TimerActual:                # breath_timer and meditation_timer
    card_type: Literal["breath_timer", "meditation_timer"]
    ratings: dict[str, int]
    completed_cycles: int | None  # breath only

class ChecklistActual:
    card_type: Literal["checklist"]
    answers: list[ChecklistAnswer]

class ChecklistAnswer:
    item_id: str
    checked: bool
    text: str | None
```

(Breath and meditation may be one `TimerActual` or two near-identical models — implementation
detail decided in the plan; the union discriminates on `card_type` either way.)

## Frontend

### Component routing

A single `CardBody` dispatcher switches on `card_type`, replacing the current `renderer`
if/else in both `frontend/src/routes/today/+page.svelte` and
`frontend/src/routes/routines/schedule/+page.svelte`. Five dedicated components:

- `RunningWorkoutCard` — segment list, pace/HR/drift/RPE log inputs, calibration-quality toggle.
- `StrengthSessionCard` — per-set grid with per-set weight/reps/RIR, "add extra exercise"
  affordance (sets `is_extra`), post-session ratings.
- `BreathTimerCard` — breathing animation driven by `phases`, ratings, completed-cycles.
- `MeditationTimerCard` — technique/anchor display, timer, ratings.
- `ChecklistCard` — items with checkbox + optional free-text answer.

All typed off the discriminated union now flowing into `api-types.ts`. `card-payloads.ts` is
replaced/retyped against the generated union (no manual casts).

### Domain theming

A small `domain → { accent, icon }` map (running, strength, breathwork, meditation), derived
from `card_type` (with `checklist.domain` for reviews). Domain identity becomes the card's
primary visual cue; slot accents (morning/midday/evening) demote to secondary. Gets a
**ux-design skill** pass before implementation.

## Migration

- Bump artifact `schema_version` to `2`.
- Re-author all 6 bundle JSONs in `docs/routine_bundles/` to typed payloads:
  - running text-blobs → `workout_type` / `rpe` / `talk_test` / `hr_guidance` /
    `calibration_quality` + typed `segments`.
  - strength fake `post_session_ratings` row → `rating_prompts`; `set_scheme` per exercise.
  - breath `pattern` string → typed `phases` (+ keep `pattern_label`).
- Re-import; existing imported cards are disposable (re-import replaces them).
- Update `docs/ROUTINE_ARTIFACT_BUNDLE_SPEC.md`.
- Update `backend/tests/domains/artifacts/test_artifact_bundles.py` to the typed schema.

## Validation

Per CLAUDE.md scope rules:
- Backend changed: `uv run ruff check`, `uv run pyright app/ tests/`, `uv run pytest tests/ -v`
  — all green, 0 errors.
- API schema changed: `bash scripts/generate-api-types.sh`, commit `api-types.ts`,
  `cd frontend && npm run check`.
- Visual verification of every new card on Today + Schedule at desktop viewport (browser MCP).
- Update `README.md` (routes/contracts) and this spec if the design shifts during build.

## Implementation Phasing (for the plan)

Each phase keeps backend + bundles + frontend green together.

1. **Framework** — `card_type` discriminator + discriminated-union payload/log contracts +
   `checklist` migrated end-to-end. Proves the pattern with the simplest type.
2. **Breath + Meditation** — timer family, share rating-prompt logging.
3. **Strength** — per-set grid + extras (`is_extra`).
4. **Running** — segments + actuals.
5. **Domain theming** — accent + icon across all five (ux-design pass).

## Risks / Open Questions

- **Discriminated-union OpenAPI output** — confirm Pydantic `Field(discriminator=...)` emits a
  TS union that `openapi-typescript` renders cleanly; verify in Phase 1 with `checklist` before
  building four more types on the assumption.
- **Override payloads** — `prescription_override_json` on assignments is still a generic dict;
  confirm whether overrides need to be typed too, or remain free-form tweaks (lean: free-form
  for now, out of scope).

## Implementation Deltas

Recorded at build completion (2026-06-29). These are deviations from the design above that were
decided or discovered during implementation:

**(a) `RunCustomField` + `post_run_fields` + `RunningActual.post_run`** — added to the running
card to capture per-run confounders (weather, terrain, etc.) that the design did not include.
`RunningWorkoutPayload.post_run_fields: list[RunCustomField]` defines the fields to collect;
`RunningActual.post_run: dict[str, float | str | None]` stores the logged values keyed by
`RunCustomField.key`. This was a user decision made during the running-card implementation.

**(b) Override merge is defensive** — `prescription_override_json` keys are validated against
the target card type's payload model at merge time. Invalid keys (keys not present on that
payload type) fall back silently to the base payload value; `card_type` is always stripped from
overrides before merging (it cannot be changed via override).

**(c) Empty `actual_json: {}` coerces to `None`** — a `model_validator(mode="before")` on
`CardLog`, `TodayCard`, and `TodayCardLogUpdateRequest` normalises `actual_json: {}` (no
`card_type`) to `None`, so legacy rows and clients that send an empty body degrade gracefully
rather than raising a `ValidationError`.

**(d) Override open question resolved** — `prescription_override_json` stays as a free-form
`dict[str, object]` in the data model, but is validated against the target payload at merge time
(keys not on the payload are silently ignored). This is the "free-form with runtime validation"
middle path: no separate typed override model, but invalid overrides never surface as bad data.
