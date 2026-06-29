# Bundle-Specific Cards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single `renderer` field on routine cards with a typed `card_type` discriminated union, giving running, strength, breathwork, meditation, and checklist cards their own typed payloads, dedicated frontend components, full per-unit logging, and per-domain theming.

**Architecture:** A `card_type` literal (`running_workout | strength_session | breath_timer | meditation_timer | checklist`) discriminates two Pydantic unions carried in the existing `payload_json` (prescription) and `actual_json` (log) fields. The union flows through OpenAPI → `api-types.ts` so the frontend narrows on `payload_json.card_type`. A `CardBody` dispatcher renders one dedicated component per type on the Today board and schedule detail panel. Bundles are re-authored to the typed schema (`schema_version: 2`) and re-imported via a new dev script.

**Tech Stack:** Backend FastAPI + Pydantic v2 (discriminated unions via `Field(discriminator=...)`), SQLite via `JsonStore` (`model_dump_json`). Frontend SvelteKit 2 / Svelte 5 runes, TypeScript, `openapi-typescript`.

## Global Constraints

- Python via `uv` only (never bare `pip`). Single venv at `backend/.venv`, Python 3.14.
- Backend changed → `cd backend && uv run ruff check` + `uv run pyright app/ tests/` + `uv run pytest tests/ -v` must all be **0 errors**, no exceptions.
- API schema changed → `bash scripts/generate-api-types.sh`, commit `frontend/src/lib/api-types.ts`, then `cd frontend && npm run check` (0 errors).
- Frontend is display/input only: zero statistical computation. Cards collect user-entered actuals (input, not computed stats); array-length briefs like "3 exercises" are display formatting and stay.
- Never hand-write `frontend/src/lib/api-types.ts` — always regenerate via the script.
- All UX/frontend changes MUST be visually verified with browser MCP tools at desktop viewport before a frontend task is considered done.
- Invoke the `ux-design` skill before the theming task (Phase 6) and before building any new card component’s visual layout.
- Conventional commit messages; commit after each task. End commit messages with the `Co-Authored-By` trailer.

---

## File Structure

**Backend — new/modified:**
- `backend/app/domains/routines/contracts.py` — MODIFY: remove `RendererFamily`; add `CardType`, shared `RatingPrompt`, five payload models, five actual models, `CardPayload`/`CardActual` unions; retype `CardTemplate`, `ScheduleOccurrence`, `TodayCard`, `CardLog`, `TodayCardLogUpdateRequest`.
- `backend/app/domains/artifacts/contracts.py` — MODIFY: drop renderer-based payload specs (`TimerSessionPayloadSpec` etc.) and `renderer` on `CardTemplateSpec`; `CardTemplateSpec.payload` becomes `CardPayload`; repurpose/relax `CapabilityRequestSpec`.
- `backend/app/domains/artifacts/application/validation.py` — MODIFY: delete `PAYLOAD_MODELS` dispatch; rely on union validation; keep `validate_card_template_payload` as a thin wrapper returning Pydantic errors.
- `backend/app/domains/artifacts/application/activation.py` — MODIFY: `_compile_card_template_artifact` sets `payload_json=spec.payload` (typed), drops `renderer`.
- `backend/app/domains/artifacts/application/bundles.py` — MODIFY: delta summaries read `payload.card_type` instead of `renderer`.
- `scripts/import_bundles.py` — CREATE: dev script that previews + imports + activates every JSON in `docs/routine_bundles/`.

**Bundles (re-authored, `schema_version: 2`):**
- `docs/routine_bundles/four_weeks_breathwork.json`, `four_weeks_meditation.json`, `four_week_strength_running_calibration_bundle.json`, `four_week_running_calibration_bundle_patched.json`, `four_week_running_meditation_transfer_bundle.json`, `four_week_running_support_calibration_bundle.json`.
- `docs/ROUTINE_ARTIFACT_BUNDLE_SPEC.md` — MODIFY.

**Frontend — new/modified:**
- `frontend/src/lib/routines/card-payloads.ts` — MODIFY: drop `Renderer`/`*Payload` casts; export `CardType`, `cardTypeOf`, `cardBrief`, domain theming map.
- `frontend/src/lib/routines/cards/CardBody.svelte` — CREATE: dispatcher.
- `frontend/src/lib/routines/cards/ChecklistCard.svelte`, `BreathTimerCard.svelte`, `MeditationTimerCard.svelte`, `StrengthSessionCard.svelte`, `RunningWorkoutCard.svelte` — CREATE.
- `frontend/src/routes/today/+page.svelte` — MODIFY: replace renderer switch (524–610) + `buildActualJson` (194–203) with `CardBody` + component-emitted actuals.
- `frontend/src/routes/routines/schedule/+page.svelte` — MODIFY: replace renderer switch (426–481) with `CardBody` (read-only mode).

**Tests:**
- `backend/tests/domains/artifacts/test_artifact_bundles.py` — MODIFY to typed schema.
- `backend/tests/domains/routines/test_card_types.py` — CREATE: union validation + log round-trip per type.
- `frontend/tests/card-payloads.test.mjs` — CREATE: `cardBrief`/theming helpers.

---

## Phase 1 — Backend contract foundation

### Task 1.1: Define `card_type`, shared primitives, and the five payload models

**Files:**
- Modify: `backend/app/domains/routines/contracts.py`
- Test: `backend/tests/domains/routines/test_card_types.py`

**Interfaces:**
- Produces: `CardType`; `RatingPrompt`; payload models `RunningWorkoutPayload`, `StrengthSessionPayload`, `BreathTimerPayload`, `MeditationTimerPayload`, `ChecklistPayload`; union `CardPayload = Annotated[Union[...], Field(discriminator="card_type")]`. Each payload member has a literal `card_type` field.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/domains/routines/test_card_types.py`:

```python
"""Discriminated-union card payload/actual contracts.

Covers one valid payload per card_type, discriminator dispatch, and rejection
of an unknown card_type. Log round-trips live in test_card_logs below.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from app.domains.routines.contracts import (
    CardPayload,
    ChecklistPayload,
    RunningWorkoutPayload,
    StrengthSessionPayload,
)

PAYLOAD_ADAPTER = TypeAdapter(CardPayload)


def test_checklist_payload_dispatches_by_card_type():
    payload = PAYLOAD_ADAPTER.validate_python(
        {
            "card_type": "checklist",
            "instructions": "Weekly review",
            "items": [{"id": "q1", "label": "What worked?"}],
            "domain": "breathwork",
        }
    )
    assert isinstance(payload, ChecklistPayload)
    assert payload.items[0].id == "q1"


def test_running_payload_promotes_structured_fields():
    payload = PAYLOAD_ADAPTER.validate_python(
        {
            "card_type": "running_workout",
            "workout_type": "easy_plus_strides",
            "calibration_quality": True,
            "segments": [
                {"id": "warmup", "label": "Easy running", "kind": "warmup", "prescription": "35-50 min"}
            ],
        }
    )
    assert isinstance(payload, RunningWorkoutPayload)
    assert payload.segments[0].kind == "warmup"


def test_strength_payload_carries_set_scheme_and_ratings():
    payload = PAYLOAD_ADAPTER.validate_python(
        {
            "card_type": "strength_session",
            "exercises": [{"id": "pa1", "label": "Bench", "set_scheme": "3x5-8"}],
            "rating_prompts": [{"key": "shoulder_comfort", "label": "Shoulder comfort"}],
        }
    )
    assert isinstance(payload, StrengthSessionPayload)
    assert payload.exercises[0].set_scheme == "3x5-8"


def test_unknown_card_type_is_rejected():
    with pytest.raises(ValidationError):
        PAYLOAD_ADAPTER.validate_python({"card_type": "nope"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/domains/routines/test_card_types.py -v`
Expected: FAIL — `ImportError: cannot import name 'CardPayload'`.

- [ ] **Step 3: Implement payload models**

In `backend/app/domains/routines/contracts.py`, change the imports at top to include `Annotated`/`Union` and `Field`:

```python
from typing import Annotated, Literal, Union

from pydantic import Field
```

Remove the `RendererFamily` definition (line 19). Add, after `SlotName`:

```python
CardType = Literal[
    "running_workout",
    "strength_session",
    "breath_timer",
    "meditation_timer",
    "checklist",
]
RunSegmentKind = Literal["warmup", "main", "strides", "cooldown", "intervals"]
BreathPhaseKind = Literal["inhale", "hold_full", "exhale", "hold_empty"]


class RatingPrompt(StrictDefaultsRequired):
    """One post-session rating prompt shared by workout card payloads."""

    key: str
    label: str
    scale_min: int = 1
    scale_max: int = 5


class RunSegment(StrictDefaultsRequired):
    """One segment of a running workout; prescription is a range string."""

    id: str
    label: str
    kind: RunSegmentKind
    detail: str | None = None
    prescription: str


class RunningWorkoutPayload(StrictDefaultsRequired):
    """Typed prescription for a running workout card."""

    card_type: Literal["running_workout"] = "running_workout"
    workout_type: str
    rpe: str | None = None
    talk_test: str | None = None
    hr_guidance: str | None = None
    calibration_quality: bool = False
    instructions: str | None = None
    segments: list[RunSegment] = []


class StrengthExercise(StrictDefaultsRequired):
    """One prescribed strength exercise; set_scheme is a range string."""

    id: str
    label: str
    detail: str | None = None
    set_scheme: str


class StrengthSessionPayload(StrictDefaultsRequired):
    """Typed prescription for a strength session card."""

    card_type: Literal["strength_session"] = "strength_session"
    session_focus: str | None = None
    duration_minutes: int | None = None
    rir_guidance: str | None = None
    instructions: str | None = None
    exercises: list[StrengthExercise] = []
    rating_prompts: list[RatingPrompt] = []


class BreathPhase(StrictDefaultsRequired):
    """One timed phase of a breathing pattern."""

    kind: BreathPhaseKind
    seconds: int


class BreathTimerPayload(StrictDefaultsRequired):
    """Typed prescription for a breathwork timer card."""

    card_type: Literal["breath_timer"] = "breath_timer"
    duration_minutes: int
    pattern_label: str
    phases: list[BreathPhase] = []
    instructions: str | None = None
    rating_prompts: list[RatingPrompt] = []


class MeditationTimerPayload(StrictDefaultsRequired):
    """Typed prescription for a meditation timer card."""

    card_type: Literal["meditation_timer"] = "meditation_timer"
    duration_minutes: int
    technique: str
    anchor: str | None = None
    instructions: str | None = None
    rating_prompts: list[RatingPrompt] = []


class ChecklistItem(StrictDefaultsRequired):
    """One checklist item inside a checklist card payload."""

    id: str
    label: str
    detail: str | None = None


class ChecklistPayload(StrictDefaultsRequired):
    """Typed prescription for a checklist card (reviews, setup, skip days)."""

    card_type: Literal["checklist"] = "checklist"
    instructions: str | None = None
    items: list[ChecklistItem] = []
    domain: str | None = None


CardPayload = Annotated[
    Union[
        RunningWorkoutPayload,
        StrengthSessionPayload,
        BreathTimerPayload,
        MeditationTimerPayload,
        ChecklistPayload,
    ],
    Field(discriminator="card_type"),
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/domains/routines/test_card_types.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/domains/routines/contracts.py backend/tests/domains/routines/test_card_types.py
git commit -m "feat(cards): add card_type discriminated payload union

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 1.2: Define the five actual (log) models and `CardActual` union

**Files:**
- Modify: `backend/app/domains/routines/contracts.py`
- Test: `backend/tests/domains/routines/test_card_types.py`

**Interfaces:**
- Produces: `RunningActual`, `StrengthActual` (with `LoggedStrengthExercise`, `StrengthSetLog`), `TimerActual`, `ChecklistActual` (with `ChecklistAnswer`); union `CardActual = Annotated[Union[...], Field(discriminator="card_type")]`.

- [ ] **Step 1: Write the failing test** (append to `test_card_types.py`)

```python
from app.domains.routines.contracts import (
    CardActual,
    ChecklistActual,
    StrengthActual,
)

ACTUAL_ADAPTER = TypeAdapter(CardActual)


def test_strength_actual_marks_extra_work():
    actual = ACTUAL_ADAPTER.validate_python(
        {
            "card_type": "strength_session",
            "exercises": [
                {
                    "exercise_id": "pa1",
                    "is_extra": False,
                    "sets": [{"set_index": 1, "weight": 60.0, "reps": 8, "rir": 2}],
                },
                {
                    "exercise_id": None,
                    "label": "Face pulls (felt good)",
                    "is_extra": True,
                    "sets": [{"set_index": 1, "weight": 20.0, "reps": 15}],
                },
            ],
            "ratings": {"shoulder_comfort": 4},
        }
    )
    assert isinstance(actual, StrengthActual)
    extras = [e for e in actual.exercises if e.is_extra]
    assert extras[0].label == "Face pulls (felt good)"
    assert extras[0].exercise_id is None


def test_checklist_actual_round_trips():
    actual = ACTUAL_ADAPTER.validate_python(
        {
            "card_type": "checklist",
            "answers": [{"item_id": "q1", "checked": True, "text": "Resonance"}],
        }
    )
    assert isinstance(actual, ChecklistActual)
    assert actual.answers[0].text == "Resonance"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/domains/routines/test_card_types.py -v`
Expected: FAIL — `cannot import name 'CardActual'`.

- [ ] **Step 3: Implement actual models** (append to `contracts.py`, after `CardPayload`)

```python
class RunningActual(StrictDefaultsRequired):
    """Logged actuals for a completed running workout."""

    card_type: Literal["running_workout"] = "running_workout"
    distance_km: float | None = None
    duration_min: float | None = None
    avg_hr: int | None = None
    hr_drift_pct: float | None = None
    calibration_quality: bool = False
    rpe: int | None = None
    notes: str | None = None


class StrengthSetLog(StrictDefaultsRequired):
    """One logged set of a strength exercise."""

    set_index: int
    weight: float | None = None
    reps: int | None = None
    rir: int | None = None


class LoggedStrengthExercise(StrictDefaultsRequired):
    """One logged exercise; extras carry a free-text label and is_extra=True."""

    exercise_id: str | None = None
    label: str | None = None
    is_extra: bool = False
    sets: list[StrengthSetLog] = []


class StrengthActual(StrictDefaultsRequired):
    """Logged actuals for a strength session, including off-script extras."""

    card_type: Literal["strength_session"] = "strength_session"
    exercises: list[LoggedStrengthExercise] = []
    ratings: dict[str, int] = {}


class TimerActual(StrictDefaultsRequired):
    """Logged ratings for a breath or meditation timer session."""

    card_type: Literal["breath_timer", "meditation_timer"]
    ratings: dict[str, int] = {}
    completed_cycles: int | None = None


class ChecklistAnswer(StrictDefaultsRequired):
    """One answered checklist item."""

    item_id: str
    checked: bool = False
    text: str | None = None


class ChecklistActual(StrictDefaultsRequired):
    """Logged answers for a checklist card."""

    card_type: Literal["checklist"] = "checklist"
    answers: list[ChecklistAnswer] = []


CardActual = Annotated[
    Union[
        RunningActual,
        StrengthActual,
        TimerActual,
        ChecklistActual,
    ],
    Field(discriminator="card_type"),
]
```

> Note: `TimerActual.card_type` accepts both `breath_timer` and `meditation_timer`; Pydantic maps both literals to it in the discriminated union. This is intentional — the two timer logs are structurally identical.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/domains/routines/test_card_types.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/domains/routines/contracts.py backend/tests/domains/routines/test_card_types.py
git commit -m "feat(cards): add card_type discriminated actual/log union

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 1.3: Retype the live routine contracts onto the unions

**Files:**
- Modify: `backend/app/domains/routines/contracts.py:35-189`
- Test: `backend/tests/domains/routines/test_card_types.py`

**Interfaces:**
- Consumes: `CardPayload`, `CardActual` (Tasks 1.1–1.2).
- Produces: `CardTemplate.payload_json: CardPayload`; `ScheduleOccurrence.payload_json: CardPayload`; `TodayCard` (inherits); `CardLog.actual_json: CardActual | None`; `TodayCardLogUpdateRequest.actual_json: CardActual | None`. `renderer` removed from all.

- [ ] **Step 1: Write the failing test** (append)

```python
from app.domains.routines.contracts import CardTemplate, ScheduleOccurrence


def test_card_template_payload_is_typed_union():
    card = CardTemplate.model_validate(
        {
            "id": "c1",
            "name": "Breathwork Weekly Review",
            "slot_default": "evening",
            "payload_json": {
                "card_type": "checklist",
                "items": [{"id": "q1", "label": "What worked?"}],
            },
        }
    )
    assert card.payload_json.card_type == "checklist"
    assert not hasattr(card, "renderer")


def test_schedule_occurrence_rejects_legacy_renderer():
    with pytest.raises(ValidationError):
        ScheduleOccurrence.model_validate(
            {
                "occurrence_key": "k",
                "date": "2026-06-29",
                "slot": "evening",
                "source_kind": "scheduled",
                "card_template_id": "c1",
                "name": "x",
                "renderer": "checklist_block",  # removed field, extra forbidden? see note
                "payload_json": {"card_type": "checklist"},
            }
        )
```

> Note: `ScheduleOccurrence` extends `DefaultsRequired` (not strict), so unknown keys are ignored, not rejected. Change the second test to assert the parsed model exposes `payload_json.card_type` and has no `renderer` attribute instead of expecting a raise:

```python
def test_schedule_occurrence_has_no_renderer():
    occ = ScheduleOccurrence.model_validate(
        {
            "occurrence_key": "k",
            "date": "2026-06-29",
            "slot": "evening",
            "source_kind": "scheduled",
            "card_template_id": "c1",
            "name": "x",
            "payload_json": {"card_type": "checklist"},
        }
    )
    assert occ.payload_json.card_type == "checklist"
    assert not hasattr(occ, "renderer")
```

Use this second form; delete the `_rejects_legacy_renderer` variant.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/domains/routines/test_card_types.py -v`
Expected: FAIL — `CardTemplate` still has `renderer` / `payload_json` is `dict`.

- [ ] **Step 3: Apply the retype edits**

In `CardTemplate` (line 35): delete `renderer: RendererFamily`; change `payload_json: dict[str, object] = {}` → `payload_json: CardPayload`.

In `ScheduleOccurrence` (line 163): delete `renderer: RendererFamily`; change `payload_json: dict[str, object] = {}` → `payload_json: CardPayload`.

In `CardLog` (line 117): change `actual_json: dict[str, object] = {}` → `actual_json: CardActual | None = None`.

In `TodayCard` (line 184): change `actual_json: dict[str, object] = {}` → `actual_json: CardActual | None = None`.

In `TodayCardLogUpdateRequest` (line 143): change `actual_json: dict[str, object] = {}` → `actual_json: CardActual | None = None`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/domains/routines/test_card_types.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/domains/routines/contracts.py backend/tests/domains/routines/test_card_types.py
git commit -m "feat(cards): retype live routine contracts onto card_type unions

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 1.4: Migrate the artifacts contracts + validation + activation

**Files:**
- Modify: `backend/app/domains/artifacts/contracts.py:30-119`
- Modify: `backend/app/domains/artifacts/application/validation.py:24-76`
- Modify: `backend/app/domains/artifacts/application/activation.py:30-46`
- Modify: `backend/app/domains/artifacts/application/bundles.py` (delta summary)

**Interfaces:**
- Consumes: `CardPayload` from routines contracts.
- Produces: `CardTemplateSpec.payload: CardPayload` (no `renderer`); `validate_card_template_payload(spec_or_payload) -> tuple[list[str], CardPayload | None]`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/domains/artifacts/test_card_template_spec.py`:

```python
"""CardTemplateSpec accepts typed payloads and rejects legacy renderer specs."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domains.artifacts.contracts import CardTemplateSpec


def test_card_template_spec_typed_payload():
    spec = CardTemplateSpec.model_validate(
        {
            "id": "c1",
            "name": "Weekly Review",
            "slot_default": "evening",
            "payload": {
                "card_type": "checklist",
                "items": [{"id": "q1", "label": "What worked?"}],
            },
        }
    )
    assert spec.payload.card_type == "checklist"


def test_card_template_spec_rejects_legacy_renderer_payload():
    with pytest.raises(ValidationError):
        CardTemplateSpec.model_validate(
            {
                "id": "c1",
                "name": "Old",
                "renderer": "checklist_block",
                "slot_default": "evening",
                "payload": {"items": []},  # no card_type discriminator
            }
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/domains/artifacts/test_card_template_spec.py -v`
Expected: FAIL (spec still has `renderer`, payload is dict).

- [ ] **Step 3: Edit contracts.py**

In `backend/app/domains/artifacts/contracts.py`: delete `TimerSegmentSpec`, `RatingPromptSpec`, `ChecklistItemSpec`, `ExerciseItemSpec`, `TimerSessionPayloadSpec`, `ChecklistBlockPayloadSpec`, `ExerciseBlockPayloadSpec` (lines 30–85). Update the import block (line 18) to drop `RendererFamily` and add `CardPayload`:

```python
from app.domains.routines.contracts import (
    CardPayload,
    RoutineActivationAssignment,
    SlotName,
)
```

Change `CardTemplateSpec` (line 88):

```python
class CardTemplateSpec(StrictDefaultsRequired):
    """Assistant-authored card template draft before activation."""

    id: str
    name: str
    slot_default: SlotName
    summary: str | None = None
    tags: list[str] = []
    payload: CardPayload
```

Change `CapabilityRequestSpec.requested_renderer` (line 116) → `requested_card_type: str`.

- [ ] **Step 4: Edit validation.py**

Replace the `PAYLOAD_MODELS` dispatch (lines 24–27) and `validate_card_template_payload` body so validation defers to the union. Minimal form:

```python
from app.domains.routines.contracts import CardPayload

_PAYLOAD_ADAPTER = TypeAdapter(CardPayload)


def validate_card_template_payload(payload: object) -> tuple[list[str], CardPayload | None]:
    """Validate a raw card payload dict against the card_type union."""
    try:
        return [], _PAYLOAD_ADAPTER.validate_python(payload)
    except ValidationError as exc:
        return [_format_error(e) for e in exc.errors()], None
```

Keep the existing `_format_error`/`_try_validate` helper if present; adapt the call site at `bundles.py:336` to the new signature (it already uses `validate_card_template_payload(payload)[0]`).

- [ ] **Step 5: Edit activation.py**

In `_compile_card_template_artifact` (lines 30–46): the artifact `payload_json` is the full `CardTemplateSpec` dict. Build the live card:

```python
spec = CardTemplateSpec.model_validate(artifact.payload_json)
card = CardTemplate(
    id=spec.id,
    name=spec.name,
    slot_default=spec.slot_default,
    summary=spec.summary,
    tags=spec.tags,
    payload_json=spec.payload,
    source_artifact_id=artifact.id,
)
```

(Remove the `renderer=spec.renderer` line.)

- [ ] **Step 6: Edit bundles.py delta summary**

Find any reference to `.renderer` in `bundles.py` (delta summary / capability handling) and read `payload.card_type` instead. Grep first: `cd backend && grep -n "renderer" app/domains/artifacts/application/bundles.py`.

- [ ] **Step 7: Run targeted + full backend suite**

Run: `cd backend && uv run pytest tests/domains/artifacts/test_card_template_spec.py -v`
Expected: PASS. Then `uv run ruff check && uv run pyright app/ tests/`. Fix any residual `renderer`/`RendererFamily` references surfaced (grep `cd backend && grep -rn "renderer\|RendererFamily" app/`).

- [ ] **Step 8: Commit**

```bash
git add backend/app/domains/artifacts backend/tests/domains/artifacts/test_card_template_spec.py
git commit -m "feat(cards): migrate artifacts spec/validation/activation to card_type

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 1.5: Re-author the breathwork & meditation bundles + import script + green suite

> Checklist + the two timer bundles are the smallest valid payloads, so we re-author them first to unblock end-to-end import. (Strength/running bundles are re-authored in their own phases.)

**Files:**
- Modify: `docs/routine_bundles/four_weeks_breathwork.json`, `docs/routine_bundles/four_weeks_meditation.json`
- Create: `scripts/import_bundles.py`
- Modify: `backend/tests/domains/artifacts/test_artifact_bundles.py`

**Interfaces:**
- Produces: a runnable `scripts/import_bundles.py` importing+activating all bundles in `docs/routine_bundles/`.

- [ ] **Step 1: Re-author breathwork + meditation JSON**

For every card template: set `schema_version: 2` at bundle top level; replace `"renderer": "timer_session"` cards with `payload.card_type: "breath_timer"` (breathwork) or `"meditation_timer"` (meditation), converting `pattern` → `pattern_label` + typed `phases` (breath), `pattern` → `technique`/`anchor` (meditation), keeping `duration_minutes`, `instructions`, `rating_prompts`. Replace `"renderer": "checklist_block"` review cards with `payload.card_type: "checklist"`, `domain: "breathwork"`/`"meditation"`. Drop top-level `renderer` keys.

Example breath card (`Box Breathing — 4/4/4/4`):

```json
{
  "id": "breathwork-box-4444",
  "name": "Box Breathing — 4/4/4/4",
  "slot_default": "evening",
  "tags": ["breathwork", "box"],
  "payload": {
    "card_type": "breath_timer",
    "duration_minutes": 5,
    "pattern_label": "4s in / 4s hold / 4s out / 4s hold",
    "phases": [
      {"kind": "inhale", "seconds": 4},
      {"kind": "hold_full", "seconds": 4},
      {"kind": "exhale", "seconds": 4},
      {"kind": "hold_empty", "seconds": 4}
    ],
    "instructions": "Move cleanly through each transition...",
    "rating_prompts": [
      {"key": "breath_smoothness", "label": "Breath smoothness", "scale_min": 1, "scale_max": 5}
    ]
  }
}
```

- [ ] **Step 2: Write the import script**

Create `scripts/import_bundles.py`:

```python
"""Dev utility: preview, import, and activate every bundle in docs/routine_bundles/.

Idempotent re-import: existing imported card/routine artifacts are replaced.
Run: cd backend && uv run python ../scripts/import_bundles.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.domains.artifacts.adapters import SqliteArtifactRepository
from app.domains.artifacts.application.bundles import (
    import_artifact_bundle,
    preview_artifact_bundle,
)
from app.domains.artifacts.contracts import ArtifactBundleSpec
from app.domains.routines.adapters import SqliteRoutineRepository

BUNDLES_DIR = Path(__file__).resolve().parent.parent / "docs" / "routine_bundles"


def main() -> int:
    artifact_repo = SqliteArtifactRepository()
    routines_repo = SqliteRoutineRepository()
    failed = False
    for path in sorted(BUNDLES_DIR.glob("*.json")):
        bundle = ArtifactBundleSpec.model_validate(json.loads(path.read_text()))
        preview = preview_artifact_bundle(artifact_repo, routines_repo, bundle)
        if not preview.valid:
            failed = True
            print(f"SKIP {path.name}: {[i.message for i in preview.issues]}")
            continue
        result = import_artifact_bundle(artifact_repo, routines_repo, bundle)
        print(f"OK   {path.name}: imported {result.total_imported}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

> If activation (compiling routines into dated assignments) is a separate call from import in `application/`, add the activation call after import — mirror what `test_artifact_bundles.py` does for the full flow.

- [ ] **Step 3: Update bundle tests to typed schema**

In `backend/tests/domains/artifacts/test_artifact_bundles.py`, change all inline card specs from `renderer` + untyped payload to `payload.card_type` typed payloads. Add an assertion that imported breathwork cards expose `payload_json.card_type == "breath_timer"`.

- [ ] **Step 4: Run full backend suite + lint + types**

Run: `cd backend && uv run pytest tests/ -v && uv run ruff check && uv run pyright app/ tests/`
Expected: all PASS, 0 errors.

- [ ] **Step 5: Smoke-test the import script**

Run: `cd backend && uv run python ../scripts/import_bundles.py`
Expected: `OK four_weeks_breathwork.json` and `OK four_weeks_meditation.json` lines (other bundles may SKIP until re-authored — acceptable at this phase; note it in output).

- [ ] **Step 6: Commit**

```bash
git add docs/routine_bundles/four_weeks_breathwork.json docs/routine_bundles/four_weeks_meditation.json scripts/import_bundles.py backend/tests/domains/artifacts/test_artifact_bundles.py
git commit -m "feat(cards): re-author timer bundles to card_type + add import script

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 1.6: Regenerate api-types and verify the TS union (RISK GATE)

**Files:**
- Modify: `frontend/src/lib/api-types.ts` (generated)

- [ ] **Step 1: Regenerate**

Run: `bash scripts/generate-api-types.sh`

- [ ] **Step 2: Verify the discriminated union rendered**

Run: `cd frontend && grep -n "card_type" src/lib/api-types.ts | head`
Expected: `ChecklistPayload`, `BreathTimerPayload`, etc. schemas each with a `card_type` literal, and `payload_json` typed as a union of them. If `openapi-typescript` emitted an opaque/merged type instead of a usable union, STOP and resolve here (e.g. add explicit `json_schema_extra` discriminator mapping) before Phase 2 — this is the design’s key risk.

- [ ] **Step 3: Commit**

```bash
git add frontend/openapi.json frontend/src/lib/api-types.ts
git commit -m "chore(api): regenerate types for card_type unions

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 2 — Frontend framework + ChecklistCard

### Task 2.1: Retype `card-payloads.ts` to the card_type model

**Files:**
- Modify: `frontend/src/lib/routines/card-payloads.ts`
- Test: `frontend/tests/card-payloads.test.mjs`

**Interfaces:**
- Produces: `CardType`, `cardTypeOf(card)`, `cardBrief(card)`, `DOMAIN_THEME` map, `domainOf(payload)`.

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/card-payloads.test.mjs`:

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { cardBrief, domainOf } from '../src/lib/routines/card-payloads.ts';

test('cardBrief summarizes a breath timer by duration', () => {
  assert.equal(cardBrief({ payload_json: { card_type: 'breath_timer', duration_minutes: 5 } }), '5 min');
});

test('cardBrief counts strength exercises', () => {
  assert.equal(
    cardBrief({ payload_json: { card_type: 'strength_session', exercises: [{}, {}] } }),
    '2 exercises'
  );
});

test('domainOf maps card_type to a domain key', () => {
  assert.equal(domainOf({ card_type: 'running_workout' }), 'running');
  assert.equal(domainOf({ card_type: 'checklist', domain: 'strength' }), 'strength');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && node --test tests/card-payloads.test.mjs`
Expected: FAIL — `domainOf` not exported.

- [ ] **Step 3: Rewrite `card-payloads.ts`**

Replace the `Renderer`/`*Payload` casts (lines 7–31, 58–81) with union-based helpers. Keep `SlotName`, `SLOT_*` exports. Add:

```typescript
import type { ScheduleOccurrence } from '$lib/api';
import { COLORS, withAlpha } from '$lib/colors';

export type CardPayload = ScheduleOccurrence['payload_json'];
export type CardType = CardPayload['card_type'];
export type Domain = 'running' | 'strength' | 'breathwork' | 'meditation';

const CARD_TYPE_DOMAIN: Record<CardType, Domain | null> = {
  running_workout: 'running',
  strength_session: 'strength',
  breath_timer: 'breathwork',
  meditation_timer: 'meditation',
  checklist: null
};

export function domainOf(payload: CardPayload): Domain | null {
  if (payload.card_type === 'checklist') {
    return (payload.domain as Domain) ?? null;
  }
  return CARD_TYPE_DOMAIN[payload.card_type];
}

export const DOMAIN_THEME: Record<Domain, { accent: string; icon: string }> = {
  running: { accent: COLORS.respiration, icon: '🏃' },
  strength: { accent: COLORS.stress, icon: '🏋' },
  breathwork: { accent: COLORS.spo2, icon: '🫁' },
  meditation: { accent: COLORS.hrv, icon: '🧘' }
};

export function cardBrief(card: { payload_json: CardPayload }): string {
  const p = card.payload_json;
  switch (p.card_type) {
    case 'breath_timer':
    case 'meditation_timer':
      return p.duration_minutes ? `${p.duration_minutes} min` : '';
    case 'strength_session':
      return p.exercises?.length ? `${p.exercises.length} exercises` : '';
    case 'running_workout':
      return p.segments?.length ? `${p.segments.length} segments` : '';
    case 'checklist':
      return p.items?.length ? `${p.items.length} items` : '';
  }
}
```

(Final accent/icon choices are revisited in Phase 6 with the ux-design skill; placeholders above are functional.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && node --test tests/card-payloads.test.mjs`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/routines/card-payloads.ts frontend/tests/card-payloads.test.mjs
git commit -m "feat(cards): retype card-payloads helpers to card_type model

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

### Task 2.2: Build `CardBody` dispatcher + `ChecklistCard`, wire both surfaces

**Files:**
- Create: `frontend/src/lib/routines/cards/CardBody.svelte`, `frontend/src/lib/routines/cards/ChecklistCard.svelte`
- Modify: `frontend/src/routes/today/+page.svelte:524-610,194-203`
- Modify: `frontend/src/routes/routines/schedule/+page.svelte:426-481`

**Interfaces:**
- `CardBody` props: `card` (occurrence/today card), `mode: 'log' | 'view'`, and a callback `onActual?: (actual: CardActual) => void` for log mode. Dispatches on `card.payload_json.card_type`.
- `ChecklistCard` emits a `ChecklistActual` (`{ card_type: 'checklist', answers: [...] }`).

- [ ] **Step 1: Invoke the ux-design skill** for the checklist card layout (items, checkbox + free-text answer, view vs log mode).

- [ ] **Step 2: Create `CardBody.svelte`** — a switch on `card.payload_json.card_type` rendering the matching component (only `ChecklistCard` wired now; others added in later phases with a temporary fallback to the old generic block until replaced).

- [ ] **Step 3: Create `ChecklistCard.svelte`** — `view` mode lists items + detail; `log` mode adds a checkbox and optional text input per item, emitting `ChecklistActual` via `onActual`.

- [ ] **Step 4: Wire Today board** — replace the renderer `{#if}` block (524–610) with `<CardBody {card} mode="log" onActual={...} />`. Replace `buildActualJson` (194–203) so it returns the actual emitted by the component for checklist cards (keep old branches for not-yet-migrated types behind the dispatcher fallback).

- [ ] **Step 5: Wire Schedule page** — replace the renderer `{#if}` block (426–481) with `<CardBody occ={...} mode="view" />`.

- [ ] **Step 6: Validate + visually verify**

Run: `cd frontend && npm run check`
Then run the app (`cd backend && uv run uvicorn app.main:app --reload` + `cd frontend && npm run dev`), import bundles via `scripts/import_bundles.py`, and use browser MCP to screenshot a checklist card on **Today** (log mode: check items, enter text, save) and **Schedule** (view mode). Confirm save persists (reload).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/routines/cards/CardBody.svelte frontend/src/lib/routines/cards/ChecklistCard.svelte frontend/src/routes/today/+page.svelte frontend/src/routes/routines/schedule/+page.svelte
git commit -m "feat(cards): CardBody dispatcher + ChecklistCard on both surfaces

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 3 — Breath + Meditation cards

### Task 3.1: `BreathTimerCard` (animation + ratings logging)

**Files:**
- Create: `frontend/src/lib/routines/cards/BreathTimerCard.svelte`
- Modify: `frontend/src/lib/routines/cards/CardBody.svelte`

**Interfaces:**
- Emits `TimerActual` (`{ card_type: 'breath_timer', ratings: {...}, completed_cycles? }`).

- [ ] **Step 1: Invoke ux-design skill** for the breathing-animation timer + ratings layout.
- [ ] **Step 2: Build `BreathTimerCard.svelte`** — drive a phase animation from `payload_json.phases` (expand on inhale, hold, contract on exhale, hold), show `pattern_label`, `duration_minutes`, `instructions`; `log` mode renders a rating slider per `rating_prompts` entry + optional `completed_cycles`, emitting `TimerActual`.
- [ ] **Step 3: Register in `CardBody`** for `card_type === 'breath_timer'`.
- [ ] **Step 4: Validate + visually verify** — `cd frontend && npm run check`; screenshot a box-breathing card on Today (watch the animation cycle, submit ratings) and Schedule (view).
- [ ] **Step 5: Commit** (`feat(cards): BreathTimerCard with phase animation`).

### Task 3.2: `MeditationTimerCard` (technique + ratings logging)

**Files:**
- Create: `frontend/src/lib/routines/cards/MeditationTimerCard.svelte`
- Modify: `frontend/src/lib/routines/cards/CardBody.svelte`

**Interfaces:**
- Emits `TimerActual` (`{ card_type: 'meditation_timer', ratings: {...} }`).

- [ ] **Step 1: Invoke ux-design skill** for the meditation card.
- [ ] **Step 2: Build `MeditationTimerCard.svelte`** — show `technique`, `anchor`, `duration_minutes`, `instructions`; `log` mode renders rating sliders, emits `TimerActual`.
- [ ] **Step 3: Register in `CardBody`** for `card_type === 'meditation_timer'`.
- [ ] **Step 4: Validate + visually verify** — `npm run check`; screenshot a meditation card on both surfaces.
- [ ] **Step 5: Commit** (`feat(cards): MeditationTimerCard`).

---

## Phase 4 — Strength card (per-set grid + extras)

### Task 4.1: Re-author the strength bundle to `strength_session`

**Files:**
- Modify: `docs/routine_bundles/four_week_strength_running_calibration_bundle.json`
- Modify: `backend/tests/domains/artifacts/test_artifact_bundles.py` (add strength assertion)

- [ ] **Step 1:** Convert each strength `exercise_block` card to `payload.card_type: "strength_session"`: move `instructions`, set `session_focus`/`duration_minutes`/`rir_guidance`, convert each exercise to `{id,label,detail,set_scheme}` (e.g. `reps: "3x5-8"` → `set_scheme: "3x5-8"`), and lift the fake `post_session_ratings` exercise row into `rating_prompts`. Convert the skip + weekly-review `checklist_block` cards to `card_type: "checklist"`, `domain: "strength"`. Set bundle `schema_version: 2`.
- [ ] **Step 2:** Run `cd backend && uv run pytest tests/domains/artifacts -v` then `uv run python ../scripts/import_bundles.py` — expect `OK four_week_strength_running_calibration_bundle.json`.
- [ ] **Step 3: Commit** (`feat(cards): re-author strength bundle to strength_session`).

### Task 4.2: `StrengthSessionCard` with per-set logging + extras

**Files:**
- Create: `frontend/src/lib/routines/cards/StrengthSessionCard.svelte`
- Modify: `frontend/src/lib/routines/cards/CardBody.svelte`

**Interfaces:**
- Emits `StrengthActual` (`{ card_type: 'strength_session', exercises: LoggedStrengthExercise[], ratings }`). Each prescribed exercise pre-seeds a `LoggedStrengthExercise` with `exercise_id` set; an **"+ Add extra exercise"** button appends one with `exercise_id: null`, free-text `label`, `is_extra: true`.

- [ ] **Step 1: Invoke ux-design skill** for the set×rep×load grid + extras affordance + ratings.
- [ ] **Step 2: Build `StrengthSessionCard.svelte`** — `view` mode lists exercises with `set_scheme` + detail; `log` mode renders a per-set grid (weight/reps/RIR inputs, add-set), an add-extra-exercise control, and rating sliders; emits `StrengthActual`. Mark extra rows visually (the `is_extra` flag).
- [ ] **Step 3: Register in `CardBody`** for `card_type === 'strength_session'`.
- [ ] **Step 4: Validate + visually verify** — `npm run check`; screenshot a Push A card on Today: log a couple of sets, add an extra exercise, submit, reload to confirm `is_extra` persisted (inspect via Today reload or `card-logs`). Screenshot Schedule view.
- [ ] **Step 5: Commit** (`feat(cards): StrengthSessionCard with per-set logging and extras`).

---

## Phase 5 — Running card (segments + actuals)

### Task 5.1: Re-author the three running bundles to `running_workout`

**Files:**
- Modify: `docs/routine_bundles/four_week_running_calibration_bundle_patched.json`, `four_week_running_meditation_transfer_bundle.json`, `four_week_running_support_calibration_bundle.json`
- Modify: `backend/tests/domains/artifacts/test_artifact_bundles.py` (add running assertion)

- [ ] **Step 1:** For each running workout card, convert to `payload.card_type: "running_workout"`: parse the instructions blob into `workout_type`, `rpe`, `talk_test`, `hr_guidance`, `calibration_quality` (true unless the card says wrist HR is acceptable), keep residual prose in `instructions`; convert each exercise to a `RunSegment` (`id,label,kind,detail,prescription`) where `kind` ∈ warmup/main/strides/cooldown/intervals and `prescription` takes the old `reps` string. Convert review/setup `checklist_block` cards to `card_type: "checklist"`, `domain: "running"`. Set each bundle `schema_version: 2`.
- [ ] **Step 2:** `cd backend && uv run pytest tests/domains/artifacts -v` then `uv run python ../scripts/import_bundles.py` — expect **all** bundles `OK` now (no SKIPs).
- [ ] **Step 3: Commit** (`feat(cards): re-author running bundles to running_workout`).

### Task 5.2: `RunningWorkoutCard` with segment display + actuals logging

**Files:**
- Create: `frontend/src/lib/routines/cards/RunningWorkoutCard.svelte`
- Modify: `frontend/src/lib/routines/cards/CardBody.svelte` (remove the legacy fallback — all five types now have components)

**Interfaces:**
- Emits `RunningActual` (`{ card_type: 'running_workout', distance_km?, duration_min?, avg_hr?, hr_drift_pct?, calibration_quality, rpe?, notes? }`).

- [ ] **Step 1: Invoke ux-design skill** for segment list + workout-meta header (workout_type/RPE/talk test/HR guidance) + actuals form.
- [ ] **Step 2: Build `RunningWorkoutCard.svelte`** — `view` mode shows the workout-type header, RPE/talk-test/HR-guidance chips, calibration-quality badge, and segment list with prescriptions; `log` mode renders distance/duration/avg-HR/drift/RPE inputs + a calibration-quality toggle + notes, emitting `RunningActual`.
- [ ] **Step 3: Finalize `CardBody`** — all five `card_type` branches now resolve to real components; delete the temporary legacy fallback.
- [ ] **Step 4: Validate + visually verify** — `npm run check`; screenshot a Long Easy Run on Today (log distance/HR, toggle calibration, submit) and Schedule view.
- [ ] **Step 5: Commit** (`feat(cards): RunningWorkoutCard with segments and actuals`).

---

## Phase 6 — Domain theming pass

### Task 6.1: Apply per-domain accent + icon across all five cards

**Files:**
- Modify: `frontend/src/lib/routines/card-payloads.ts` (`DOMAIN_THEME`)
- Modify: the five card components + `CardBody.svelte`
- Modify: `frontend/src/routes/today/+page.svelte`, `frontend/src/routes/routines/schedule/+page.svelte` (card chrome)

- [ ] **Step 1: Invoke ux-design skill** to choose final per-domain accent colors + icons and how domain identity composes with the existing slot accents (domain primary, slot secondary).
- [ ] **Step 2:** Finalize `DOMAIN_THEME`; apply accent border/icon to each card header via `domainOf(card.payload_json)`; demote slot accent to a secondary cue.
- [ ] **Step 3: Validate + visually verify** — `npm run check`; screenshot all five card types on Today + Schedule, confirming consistent, distinguishable domain identity at desktop viewport.
- [ ] **Step 4: Commit** (`feat(cards): per-domain accent + icon theming`).

### Task 6.2: Docs sweep

**Files:**
- Modify: `docs/ROUTINE_ARTIFACT_BUNDLE_SPEC.md`, `README.md`, `docs/superpowers/specs/2026-06-29-bundle-specific-cards-design.md` (note any deltas)

- [ ] **Step 1:** Update the bundle spec doc to the typed `card_type` schema (replace the renderer/payload-family section with the five payloads + `schema_version: 2`). Update `README.md` card/contract notes and document `scripts/import_bundles.py`.
- [ ] **Step 2: Full validation gate** — `cd backend && uv run ruff check && uv run pyright app/ tests/ && uv run pytest tests/ -v`; `cd frontend && npm run check && node --test tests/`.
- [ ] **Step 3: Commit** (`docs(cards): typed bundle schema + import script`).

---

## Self-Review

**Spec coverage:**
- Discriminator replacing renderer → Tasks 1.1, 1.3, 1.4. ✓
- Typed payloads (5) → Task 1.1. ✓
- Full per-unit logging incl. strength extras (`is_extra`) → Task 1.2 + 4.2. ✓
- Discriminated-union OpenAPI→TS risk gate → Task 1.6. ✓
- Both surfaces (Today + Schedule) → Tasks 2.2, 3.x, 4.2, 5.2. ✓
- Domain theming (ux-design) → Phase 6. ✓
- Migration: re-author all 6 bundles + `schema_version: 2` + re-import → Tasks 1.5, 4.1, 5.1 + `scripts/import_bundles.py`. ✓
- Tests for bundle import + union validation → Tasks 1.1, 1.2, 1.4, 1.5. ✓
- Docs (bundle spec, README) → Task 6.2. ✓
- Open question — `prescription_override_json` stays free-form: no task touches it (intentional, per spec). ✓

**Placeholder scan:** No TBD/TODO. Accent/icon values in Task 2.1 are explicitly marked provisional and finalized in Phase 6. ✓

**Type consistency:** `card_type` literals, `CardPayload`/`CardActual`, `payload_json`/`actual_json` field names, `LoggedStrengthExercise.is_extra`, `cardBrief`/`domainOf`/`DOMAIN_THEME` names are consistent across backend tasks and frontend tasks. ✓
