# Breath Card Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strip the breathwork card down to a prescription reference plus one optional 3-level "felt downshift" tap — removing the animated timer, `completed_cycles`, `phases`, and the 7 ratings.

**Architecture:** Two coupled changes. (1) Backend: remove `phases`/`BreathPhase`/`BreathPhaseKind` from the breath payload and `completed_cycles` from `TimerActual`, re-author the breath bundle JSONs, update tests, regenerate `api-types.ts`. (2) Frontend: rewrite `BreathTimerCard.svelte` (remove animation/timer/cycles/ratings; add the single 3-level tap) and drop `completed_cycles` from `MeditationTimerCard.svelte`.

**Tech Stack:** Backend FastAPI + Pydantic v2 (discriminated unions); SQLite via JsonStore; Frontend SvelteKit 2 / Svelte 5 runes; `openapi-typescript`.

## Global Constraints

- Python via `uv` only. Backend changed → `cd backend && uv run ruff check` + `uv run pyright app/ tests/` + `uv run pytest tests/ -v` must be 0 errors.
- API schema changed → `bash scripts/generate-api-types.sh`, commit `frontend/src/lib/api-types.ts`, then `cd frontend && npm run check` (0/0).
- Frontend display/input only — no statistical computation. Cards use one-time `untrack` init + guarded event handlers (no deep `bind:value`, no reactive `$effect` re-seed) — per the established card pattern.
- Scope: **breathwork only**. Do NOT change meditation card behavior except dropping the removed `completed_cycles` field from its emit. Strength/running untouched. Do NOT build experiment-pipeline consumption of ratings.
- Branch: work on `bundles-cards` (PR #63); the breath card components exist only there.
- The single signal stores as `TimerActual.ratings = {"felt_downshift": 1|2|3}` (1=Barely, 2=Somewhat, 3=Strongly). Optional — omit the key when unset.
- Commit messages end with the `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` trailer.

---

## File Structure

- `backend/app/domains/routines/contracts.py` — MODIFY: remove `BreathPhaseKind` (line 30), `BreathPhase` class (96-100), `BreathTimerPayload.phases` (line 109), `TimerActual.completed_cycles` (line 197).
- `docs/routine_bundles/four_weeks_breathwork.json` — MODIFY: remove `phases` + `rating_prompts` from each breath_timer card payload.
- `docs/routine_bundles/two_week_meditation_bundle.json` — MODIFY: remove `phases` + `rating_prompts` from its breath_timer cards only.
- `backend/tests/domains/artifacts/test_artifact_bundles.py` — MODIFY: drop `phases`/`rating_prompts` from inline breath specs; change the phases assertion (~668-675) to a `pattern_label` assertion.
- `frontend/src/lib/api-types.ts` — REGENERATE.
- `frontend/src/lib/routines/cards/BreathTimerCard.svelte` — REWRITE (remove animation/timer/cycles/ratings; add 3-level tap).
- `frontend/src/lib/routines/cards/MeditationTimerCard.svelte` — MODIFY: remove `completed_cycles` from its emit.

---

## Task 1: Backend — drop phases + completed_cycles, re-author breath bundles, regen types

**Files:**
- Modify: `backend/app/domains/routines/contracts.py`
- Modify: `docs/routine_bundles/four_weeks_breathwork.json`, `docs/routine_bundles/two_week_meditation_bundle.json`
- Modify: `backend/tests/domains/artifacts/test_artifact_bundles.py`
- Regenerate: `frontend/src/lib/api-types.ts`

**Interfaces:**
- Produces: `BreathTimerPayload` with fields `card_type, duration_minutes, pattern_label, instructions, rating_prompts` (NO `phases`). `TimerActual` with `card_type, ratings` (NO `completed_cycles`). `BreathPhase`/`BreathPhaseKind` no longer exist.

- [ ] **Step 1: Write failing tests** — add to `backend/tests/domains/routines/test_card_types.py`:

```python
def test_breath_payload_rejects_phases():
    # phases was removed from the schema; extra keys are forbidden
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        PAYLOAD_ADAPTER.validate_python(
            {"card_type": "breath_timer", "duration_minutes": 5,
             "pattern_label": "5s in / 5s out", "phases": [{"kind": "inhale", "seconds": 5}]}
        )

def test_breath_payload_valid_without_phases():
    p = PAYLOAD_ADAPTER.validate_python(
        {"card_type": "breath_timer", "duration_minutes": 10, "pattern_label": "5s in / 5s out"}
    )
    assert p.card_type == "breath_timer"
    assert not hasattr(p, "phases")

def test_timer_actual_has_no_completed_cycles():
    a = ACTUAL_ADAPTER.validate_python(
        {"card_type": "breath_timer", "ratings": {"felt_downshift": 2}}
    )
    assert a.ratings["felt_downshift"] == 2
    assert not hasattr(a, "completed_cycles")
```

(Reuse the module's existing `PAYLOAD_ADAPTER`/`ACTUAL_ADAPTER` TypeAdapters and `pytest` import.)

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && uv run pytest tests/domains/routines/test_card_types.py -k "phases or completed_cycles" -v`
Expected: FAIL (phases currently accepted; `completed_cycles` present).

- [ ] **Step 3: Edit `contracts.py`**
- Delete line 30 `BreathPhaseKind = Literal["inhale", "hold_full", "exhale", "hold_empty"]`.
- Delete the `BreathPhase` class (lines 96-100).
- Delete `phases: list[BreathPhase] = []` from `BreathTimerPayload` (line 109).
- Delete `completed_cycles: int | None = None` from `TimerActual` (line 197).

- [ ] **Step 4: Re-author breath bundle JSONs (hand-edit, no json.dump)** — in `docs/routine_bundles/four_weeks_breathwork.json` and the **breath_timer cards only** of `docs/routine_bundles/two_week_meditation_bundle.json`, delete the `"phases": [...]` and `"rating_prompts": [...]` arrays from each breath card's `payload`. Keep `card_type`, `duration_minutes`, `pattern_label`, `instructions`. Leave meditation/checklist cards untouched.

- [ ] **Step 5: Update `test_artifact_bundles.py`** — remove `"phases"` and `"rating_prompts"` keys from the inline breath card specs (around lines 100-113, 237-247, 303-313; grep `phases` to find all). Replace the resonance phases assertion (~668-675, `assert len(resonance.payload.phases) == 2` etc.) with a prescription check, e.g.:

```python
assert resonance.payload.pattern_label == "5s in / 5s out"
assert not hasattr(resonance.payload, "phases")
```

- [ ] **Step 6: Run the backend gate**

Run: `cd backend && uv run pytest tests/ -v` then `uv run ruff check` then `uv run pyright app/ tests/`
Expected: all pass, 0 errors. (grep first for any remaining `phases`/`completed_cycles`/`BreathPhase` refs in `app/`: `grep -rn "BreathPhase\|completed_cycles\|\.phases" backend/app` — fix any.)

- [ ] **Step 7: Regenerate API types**

Run: `bash scripts/generate-api-types.sh` then `cd frontend && npm run check`
Expected: `api-types.ts` regenerated; note that `npm run check` will now report errors in `BreathTimerCard.svelte`/`MeditationTimerCard.svelte` that still reference `phases`/`completed_cycles` — that is EXPECTED and fixed in Task 2. Confirm the only errors are in those two card files.

- [ ] **Step 8: Smoke-import + commit**

Run: `cd backend && uv run python ../scripts/import_bundles.py` (breath + two_week bundles still `OK`).

```bash
git add backend/app/domains/routines/contracts.py docs/routine_bundles/four_weeks_breathwork.json docs/routine_bundles/two_week_meditation_bundle.json backend/tests/domains/artifacts/test_artifact_bundles.py backend/tests/domains/routines/test_card_types.py frontend/openapi.json frontend/src/lib/api-types.ts
git commit -m "feat(breath): drop phases + completed_cycles from breath contracts/bundles

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Frontend — rewrite BreathTimerCard to reference + one 3-level tap

**Files:**
- Modify (rewrite): `frontend/src/lib/routines/cards/BreathTimerCard.svelte`
- Modify: `frontend/src/lib/routines/cards/MeditationTimerCard.svelte`

**Interfaces:**
- Consumes: `BreathTimerPayload` (no `phases`), `TimerActual` (no `completed_cycles`) from Task 1's regenerated `api-types.ts`.
- Produces: BreathTimerCard emits `TimerActual { card_type: 'breath_timer', ratings: { felt_downshift?: 1|2|3 } }`.

- [ ] **Step 1: Invoke the ux-design skill** for the slimmed breath card (prescription reference + a 3-level segmented tap). Note the guidance applied.

- [ ] **Step 2: Rewrite `BreathTimerCard.svelte`** — remove ALL of: the breathing-circle animation, Start/Pause/Resume, phase countdown, `setInterval` logic, `completed_cycles` input, and the `rating_prompts`-driven rating inputs. New component:
  - Props unchanged: `{ card, mode: 'log' | 'view', onActual? }`.
  - Narrow `card.payload_json` on `card_type === 'breath_timer'`.
  - VIEW mode: show `pattern_label`, `duration_minutes` (e.g. "10 min"), and `instructions`.
  - LOG mode: the same reference PLUS a single "How much did you downshift?" control — three tappable buttons labelled **Barely / Somewhat / Strongly** mapping to `1 / 2 / 3`. The currently-selected level is visually highlighted; tapping a level (or re-tapping to clear, optional) sets local `$state` and calls `emit()`.
  - `emit()` builds `TimerActual`: `{ card_type: 'breath_timer', ratings: felt_downshift == null ? {} : { felt_downshift } }` and calls `onActual?.(actual)`.
  - Initialize `felt_downshift` ONCE via `untrack` from `card.actual_json?.card_type === 'breath_timer' ? card.actual_json.ratings.felt_downshift : undefined` (mirror the pattern in `StrengthSessionCard.svelte`). Do NOT re-seed in a reactive `$effect`.
  - Keep the blue 🫁 domain styling consistent with the other cards.

- [ ] **Step 3: Update `MeditationTimerCard.svelte`** — remove `completed_cycles` from its local `TimerActual` type annotation (line ~23) and from the emitted object (line ~62). Its `ratings` behavior is otherwise unchanged.

- [ ] **Step 4: Validate**

Run: `cd frontend && npm run check`
Expected: 0 errors, 0 warnings (the Task-1 deferred errors are now resolved).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/routines/cards/BreathTimerCard.svelte frontend/src/lib/routines/cards/MeditationTimerCard.svelte
git commit -m "feat(breath): breath card = reference + one 3-level downshift tap

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 6: Controller visual verification** (not a subagent step) — the controller resets an isolated DB, re-imports, runs the app, and verifies on Today: the breath card shows pattern/duration/instructions + three downshift buttons (no circle/cycles/extra ratings); tapping a level persists (`ratings.felt_downshift`) and rehydrates on reload; schedule view shows reference only; console clean.

---

## Self-Review

**Spec coverage:**
- Remove animation/timer → Task 2 Step 2. ✓
- Remove completed_cycles (UI + contract) → Task 1 (contract/TimerActual) + Task 2 (meditation emit). ✓
- Remove phases (UI + contract + bundles) → Task 1. ✓
- Remove 7 ratings, add one 3-level felt-downshift tap (optional, ratings.felt_downshift 1|2|3) → Task 2. ✓
- Keep pattern_label/duration/instructions, theming; done/skip via row; shared notes → Task 2 (card keeps reference; row/notes are outside the card). ✓
- Regen api-types → Task 1 Step 7. ✓
- Scope: breathwork only; meditation only loses completed_cycles; experiment pipeline out of scope → constraints + tasks. ✓
- Validation (backend gate, npm check, import, visual) → Task 1 Steps 6-8, Task 2 Steps 4/6. ✓

**Placeholder scan:** none.

**Type consistency:** `felt_downshift` (1|2|3), `TimerActual.ratings`, removal of `phases`/`BreathPhase`/`BreathPhaseKind`/`completed_cycles` are consistent across both tasks.
