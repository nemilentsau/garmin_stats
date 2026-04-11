# Experiment Exposure Sync Design

**Date:** 2026-04-11

## Goal

Make experiment adherence real by auto-deriving one experiment exposure per experiment-day from routine card logs.

## Problem

The backend already stores `ExperimentExposure` rows and computes adherence from them, but nothing writes those rows from the live routine flow. The current result is structurally broken adherence: experiments linked to routines remain `0%` or `unknown` because card completion never reaches the experiment system.

## Scope

This slice is backend-only.

- Keep the existing experiment exposure API.
- Do not add manual exposure UI in this slice.
- Do not add per-card experiment metadata in this slice.
- Use the existing experiment linkage model: `Experiment.linked_routine_ids`.

## Core Decision

Experiment exposure is protocol-defined and day-grain.

- One `ExperimentExposure` represents one `experiment_id + date`.
- Exposure is derived from the full set of scheduled cards for that experiment's linked routine(s) on that date.
- Multiple same-day cards are part of the prescribed intervention dose, not ambiguity.
- Exposure must track the current card-log state, not be write-once.

## Derivation Rule

For a given experiment and date:

1. Resolve all scheduled occurrences for the date.
2. Filter to occurrences whose `routine_id` is in `experiment.linked_routine_ids`.
3. Read the current card-log status for each relevant occurrence.
4. Derive one exposure row for the day:

- No relevant occurrences for the date: no exposure row.
- All relevant occurrences still `pending` / unlogged: no exposure row. Analysis continues to show `unknown`.
- All relevant occurrences `completed`: `adherence_state="full"`, `exposure_score=1.0`.
- All relevant occurrences resolved and none contribute any completed dose:
  `adherence_state="missed"`, `exposure_score=0.0`.
- Any mixed or in-progress state between those extremes:
  `adherence_state="partial"`, `exposure_score=(completed + 0.5 * partial) / total_relevant`.

`linked_routine_entry_ids` will store the relevant occurrence keys used to derive the exposure, even though the field name is older than the current routine runtime model.

## Write Path

The exposure sync runs from the Today card-log write flow.

- User writes card log through `/api/today/{date}/cards/{occurrence_key}`.
- Backend saves the card log.
- Backend recomputes experiment exposures for that date from current schedule + card logs.
- Backend replaces the derived exposure row for each affected experiment-day so one day cannot accumulate duplicate exposure records.

## Data Integrity Rules

- Derived exposure ids must be deterministic per `experiment_id + date`.
- Sync must replace stale exposure rows for the same experiment-day, not append more rows.
- Auto-derived rows standardize on `full`, `partial`, and `missed`. They do not write `completed`.

## Non-Goals

- No frontend exposure logging UI.
- No experiment-design DSL for custom adherence formulas yet.
- No refactor of the experiments backend into its own migrated domain slice.

## Files Expected To Change

- `backend/app/services/today.py`
- `backend/app/domains/routines/api/today.py`
- `backend/app/services/experiment_exposure_sync.py` (new)
- `backend/app/infra/database.py`
- `backend/tests/test_routines_today_application.py` or new today service tests
- `backend/tests/test_experiment_exposure_sync.py` (new)

## Verification

- Red-green tests for exposure derivation and Today write orchestration.
- Full backend verification:
  - `cd backend && uv run ruff check`
  - `cd backend && uv run pyright app/ tests/`
  - `cd backend && uv run pytest tests/ -v`
