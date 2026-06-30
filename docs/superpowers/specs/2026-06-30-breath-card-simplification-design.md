# Breath Card Simplification — Design

**Date:** 2026-06-30
**Branch:** TBD (off `bundles-cards` or `main` after that merges)
**Status:** Approved design, pending implementation plan

## Problem

The breathwork card (`BreathTimerCard`) currently presents an animated breathing circle
(Start/Pause/Resume + phase countdown), a "Completed cycles" input, and **7 rating inputs**
(breath_smoothness, perceived_downshift, relaxation_depth, strain, air_hunger_comfort,
post_session_clarity, recovery_usefulness), each on a 1–5/0–5 scale.

This violates "every interface must be driven by what it gives the user":

- **The watch is the instrument.** The user times sessions on a Garmin watch and practices
  with eyes closed, so an on-screen animated timer/countdown is unusable and redundant.
- **The ratings feed nothing.** Verified end-to-end: card `actual_json.ratings` is *write-only*
  — no analytics, aggregation, or experiment code reads any rating key. The experiment engine
  only resolves `checkin.*` paths against the per-day `DailyCheckIn` model (which has none of
  these fields), and the experiment's primary outcome (`physiology.hrv.pre_post_delta`, an
  intraday pre/post window) is not computed anywhere. So 7 ratings + completed cycles is pure
  friction with zero payoff, and it suppresses consistent logging.
- **`phases` / "completed cycles" are dead data.** `phases` existed only to drive the animation
  being removed; `pattern_label` ("5s in / 5s out") already conveys the pattern in plain text.
  "Completed cycles" is meaningless for a time-based session (you breathe continuously).

## Goal

Reduce the breath card to its real job — **show the prescription, capture the one subjective
signal the watch cannot** — so logging is frictionless enough to be done consistently.

The driving experiment ("Acute HRV Response by Practice Type") separates *autonomic* effects
(breathwork → HRV, measured objectively by the watch) from *skill* effects. The one thing a
number can't capture, and which the experiment names as a subjective outcome, is whether the
user **subjectively felt the downshift** — enabling the analysis "did felt-calm track HRV?".

## Decisions (from brainstorming)

1. **Subjective input:** exactly **one** signal — *felt downshift* — plus done/skip. Not zero
   (we keep the felt-vs-measured comparison), not the old 7.
2. **Input style:** a **3-level tap** (coarse ordinal; correlates fine with the HRV delta;
   1–5 was too granular to do consistently). Optional/skippable.
3. **Scope:** **breathwork only** this pass. Meditation cards keep their current ratings (a
   later pass would give them *clarity* as their single signal). Strength/running untouched.
4. **Remove the animation/timer entirely** — the watch is the timer.
5. **Remove dead data:** `phases` and `completed_cycles` come out of the contracts, not just
   the UI.

## What the breath card becomes

**Remove:**
- Animated breathing circle + Start/Pause/Resume + phase countdown.
- "Completed cycles" input.
- All 7 rating inputs.

**Add:**
- One optional **felt-downshift** control: a 3-level tap. Labels (plain language):
  **Barely / Somewhat / Strongly**. Stored as `TimerActual.ratings = {"felt_downshift": 1|2|3}`
  (1=Barely, 2=Somewhat, 3=Strongly). Skippable — leaving it blank is valid; done/skip is the
  primary action.

**Keep:**
- Prescription reference: `pattern_label`, `duration_minutes`, `instructions`.
- Done/skip via the existing Today-row checkbox; the shared Today-panel notes field (optional).
- Blue 🫁 domain theming.

## Contract & data changes

- **`BreathTimerPayload`** (`backend/app/domains/routines/contracts.py`): remove `phases`.
  Remove the now-unused `BreathPhase` model and `BreathPhaseKind` literal if nothing else
  references them. `pattern_label`, `duration_minutes`, `instructions`, `rating_prompts` remain
  defined on the model, but `rating_prompts` is no longer rendered by the breath card (see
  below) — leave the field on the model (harmless, still typed) but drop the values from
  bundles.
- **`TimerActual`** (shared by breath + meditation): remove `completed_cycles`. `ratings:
  dict[str, int]` stays (now carries `felt_downshift` for breath; meditation still uses it).
- **Regenerate `frontend/src/lib/api-types.ts`** after the contract changes.

## Bundle changes

- `docs/routine_bundles/four_weeks_breathwork.json` and the **breath_timer cards** in
  `docs/routine_bundles/two_week_meditation_bundle.json`: remove the `phases` arrays and the
  `rating_prompts` arrays from each breath card payload. Keep `pattern_label`, `duration_minutes`,
  `instructions`. Re-import after editing.
- Update `backend/tests/domains/artifacts/test_artifact_bundles.py` assertions that reference
  breath `phases`/`rating_prompts` (if any) to the slimmed payload.

## Frontend changes

- **`BreathTimerCard.svelte`**: delete the animation/timer/cycles/ratings code. New shape:
  - VIEW mode: `pattern_label`, `duration_minutes`, `instructions`.
  - LOG mode: the same reference + the single 3-level felt-downshift tap; emit
    `TimerActual { card_type: 'breath_timer', ratings: { felt_downshift } }` on tap (omit the
    key when not yet chosen). Keep the one-time `untrack` init (prefill `felt_downshift` from an
    existing `TimerActual`). No deep `bind:value`.
- **`MeditationTimerCard.svelte`**: stop emitting `completed_cycles` (field removed). No other
  change this pass.
- `CardBody.svelte` unaffected (still routes `breath_timer` → `BreathTimerCard`).

## Out of scope (explicit)

- Meditation card simplification (separate pass; single signal = *clarity*).
- Strength/running cards.
- **Building the experiment pipeline** to actually consume per-session subjective ratings
  (mapping `ratings.felt_downshift` → an experiment-resolvable path) and to compute intraday
  pre/post-HRV windows. This pass only removes friction and captures `felt_downshift`
  forward-looking. Making the "Acute HRV Response" experiment runnable — per-session checkin
  ingestion + pre/post physiology windows — is the natural next project and is **not** done here.

## Validation

- Backend: `uv run ruff check`, `uv run pyright app/ tests/`, `uv run pytest tests/ -v` — all 0.
- API schema changed: `bash scripts/generate-api-types.sh`, commit `api-types.ts`.
- Frontend: `cd frontend && npm run check` (0/0); node tests pass.
- Re-import bundles (`scripts/import_bundles.py`) into an isolated DB; visually verify the breath
  card on Today (reference + one 3-level tap; tap persists + rehydrates; no circle/cycles/extra
  ratings) and schedule (reference only), console clean.
- Update `README.md`/bundle spec only if they describe breath `phases`/ratings.

## Risks / Open questions

- **3-level labels** ("Barely / Somewhat / Strongly") are the current choice; trivially
  adjustable in the component if the user prefers different words.
- Removing `phases` is a breaking schema change to already-imported breath cards; per the
  established migration stance, bundles are re-authored and re-imported (old card data is
  disposable). The `actual_json {}`→None coercion already handles legacy empty logs.
