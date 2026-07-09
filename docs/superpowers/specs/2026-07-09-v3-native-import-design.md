# V3-Native Import & Execution — Design (Phase 1, Slice 1)

**Status:** Draft for user review
**Governed by:** `docs/routine-pivot/schema_v3_spec.md` (§0–§8, §11), `block0/` artifacts, `pivot_roadmap.md` Phase 1, and the import-only principle (Phase 0 retraction).
**Goal:** The six Block 0 artifacts upload into the app as-is, validate through the ported linter, and execute on the Today board — v3 stored verbatim, no translation anywhere.

## Principles this design is bound by

1. **Import is the only ingress.** Content appears exclusively by uploading authored artifact files. No generators, no seeds, no derived bundles.
2. **The app adapts to the v3 schema.** v3 artifacts are stored verbatim and validated against contracts that mirror `schema_v3_spec.md`. Nothing maps v3 into v2 types — the old `CardPayload` union is untouched and untouchable by this slice.
3. **Frontend stays display-only.** All projections (segment strings, set schemes, rule text in English, variant options) are computed backend-side in read models. A read-model projection of stored content is presentation, not derivation — nothing it produces is stored or importable.

## New domain: `backend/app/domains/training/`

Owns everything v3: contracts, artifact storage, validation, block schedule, capture logs, read models. The old `routines` domain is left untouched (it still serves v2-format bundle imports — e.g. meditation bundles whenever they return — through its existing pipeline).

**Contracts** (`contracts.py`): Pydantic mirrors of spec §1–§8 — `Bundle`, `Card`, `Contract` union (overload/maintenance/measurement/recovery), `Prescription` union, `Assignment` + `Variant` + `SelectionRule`/`Predicate`, `Block` (+ `MeasurementEvent`, `Criterion`, `ExtensionRule`, `SchedulingConstraint`, `ReviewSpec`), `SignalRegistry` (signals/estimators/state vector/objective), `ExerciseLibrary`. Strict validation (unknown keys rejected), with one precedence rule: **where the markdown spec and the shipped artifacts disagree, the artifacts win** — they are the linted, adopted truth. Known deltas the contracts must carry: `Block.flat_weeks`, `Block.step_response`, `Block.scheduling_constraints` (present in `block0.json`), and `Assignment.key_session`. If the six artifacts don't parse, the contracts are wrong, not the artifacts.

**Storage** (jsonstore pattern, new tables): `training_bundles`, `training_blocks`, `training_registry`, `training_exercise_library` — each row stores the uploaded artifact JSON verbatim plus id/status. `training_card_logs` for capture (below). Re-uploading an artifact with the same id replaces it (an explicit re-import, still ingress-by-upload).

**Validator** (`domain/validator.py`): ports `block0/linter.py` L1–L12 faithfully, hardening the three known soft spots (L11 novelty computed from baseline tags vs. declared protocol changes rather than hardcoded; L9 unramped-novel-overload check covers all adaptation kinds new to the athlete's history, initially = all overloads without prior capture; L7 requires at least one `cap.*` input per state component to count as covered). Errors block activation; warnings require an explicit ack recorded with the import.

## Import flow

`POST /api/training/import` accepts the artifact set (multipart file upload; each file's kind detected from its content: bundles have `cards`, block has `identity`, registry has `signals`, library has `exercises`). Pipeline per spec §0: validate contracts → compile the block's integrated schedule → lint → store verbatim + store the lint report → activate (block becomes the active block). Partial sets allowed only until activation: activation requires a block, its bundles, the registry, and the exercise library all present.

**Import UI**: new page `Training → Import` (nav alongside Today/Schedule): drop/select the JSON files, see per-file validation, the lint report (errors/warnings, weekly miles, budget table), ack warnings, activate. Empty states everywhere point here — the board says "no active block — import one" instead of generic emptiness.

## Execution read models

`GET /api/training/today?date=` → `TrainingTodayResponse`: the active block's occurrences for that date, each a `TrainingTodayCard`:
- verbatim v3 card (contract, prescription, capture spec) and assignment (variants, selection, key_session)
- backend display projections: `segments_display` / `exercises_display` (numeric prescriptions rendered to strings, e.g. "3×2–3 @ 87% e1RM"), `rule_display` (selection decision-list in English, omitted when clauses are empty), `variant_options` (omitted when only one variant), block-relative `day`
- attached log state (status, variant_taken, notes, captured values)

`GET /api/training/schedule-window?start=&days=` mirrors it for the schedule surface. `GET /api/training/block` → block status: window, current day, burn-in/baseline state, measurement events with scheduled/backup days, lint report, exit criteria (display-only this slice).

**Capture**: `PUT /api/training/today/{date}/cards/{occurrence_key}` upserts a `training_card_logs` row: `status`, `variant_taken`, `notes`, and `capture_json` typed per the card's capture kinds — `set_rep_load[]` (set logs: weight/reps/rir), check-in (per-tissue `scale` 0–3 + `flagged`, core bool), `number` (run RPE). These shapes intentionally match the capture UI built in Phase 0 (tissue rows, per-set grid, variant control) — those components are adapted to consume `TrainingTodayCard` view models.

## Frontend

- Today page gains the training section: fetches `/api/training/today` alongside the existing (currently empty) routines feed and renders `TrainingTodayCard`s grouped under the block name, using adapted card components: run card (segment display strings + RPE + notes), strength card (exercise display + per-set logging grid + extras), check-in card (tissue rows). Variant control + rule line as built in Phase 0.
- Schedule page: same adaptation for the window view (view mode).
- Import page as above. `Programs` placeholder is untouched.

## Explicit non-goals (slice 1)

- No estimators, signals runtime, or automatic selection-rule evaluation (rules display; the human selects; `variant_taken` is the log). No event log beyond capture rows. No exit-criteria evaluation, no extension automation, no review computation. Those are Phase 1's next slices, building on this storage.
- No deletion of the v2 routines domain or its import path (survival-rule sweep happens with the dashboard reframe, Phase 2).
- No editing of artifacts in-app — changes happen in the authored files and re-import.

## Definition of done

Uploading the six `block0/` files through the UI validates (lint 0/0 matching the shipped report), activates Block 0, and the Today board renders the correct cards for the current block day with working capture (check-in scales/flags, strength set logs, run RPE, variant, notes) — verified live against `schedule_overview.md`, with all validation gates green.
