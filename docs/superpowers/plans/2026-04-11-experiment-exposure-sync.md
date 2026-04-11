# Experiment Exposure Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-derive experiment exposures from Today card logs so adherence reflects actual intervention completion.

**Architecture:** Keep the existing API stable. Add an experiment exposure sync service that recomputes one experiment-day exposure from the linked routine's scheduled cards and current card logs, then call it from the Today write path after each card-log update.

**Tech Stack:** FastAPI, Pydantic, SQLite, pytest, Ruff, Pyright

---

### Task 1: Lock Down Derivation Semantics With Failing Tests

**Files:**
- Create: `backend/tests/test_experiment_exposure_sync.py`
- Modify: `backend/tests/test_routines_today_application.py`

- [ ] **Step 1: Write a failing sync test for a fully satisfied experiment day**

Write a test that:
- creates two active cards and one active routine with both assignments on the same date
- saves an experiment linked to that routine
- saves two `completed` card logs for that date
- calls `sync_experiment_exposures_for_date("YYYY-MM-DD")`
- asserts exactly one exposure row exists for the experiment/day with `adherence_state == "full"` and `exposure_score == 1.0`

- [ ] **Step 2: Run the new sync test and verify it fails for the expected reason**

Run:

```bash
cd backend && uv run pytest tests/test_experiment_exposure_sync.py::test_sync_experiment_exposures_marks_day_full_when_all_linked_cards_completed -v
```

Expected: fail because `sync_experiment_exposures_for_date` does not exist yet.

- [ ] **Step 3: Write a failing sync test for an unresolved / mixed day**

Write a test that:
- creates two linked cards on the same experiment day
- saves one `completed` log and leaves the other unlogged
- calls sync
- asserts one exposure row exists with `adherence_state == "partial"` and `exposure_score == 0.5`

- [ ] **Step 4: Run the mixed-day test and verify it fails**

Run:

```bash
cd backend && uv run pytest tests/test_experiment_exposure_sync.py::test_sync_experiment_exposures_marks_day_partial_when_only_part_of_daily_dose_is_done -v
```

Expected: fail because the sync service is still missing.

- [ ] **Step 5: Write a failing orchestration test for Today write integration**

In `backend/tests/test_routines_today_application.py`, add a test that:
- creates a two-card routine day and a linked experiment
- calls the public Today write path twice, updating first one card and then the second
- asserts the exposure row transitions from `partial` to `full`
- updates one card back to `skipped`
- asserts the same experiment-day exposure transitions back to `partial`

- [ ] **Step 6: Run the Today integration test and verify it fails**

Run:

```bash
cd backend && uv run pytest tests/test_routines_today_application.py::test_today_card_logs_recompute_linked_experiment_exposure_for_the_day -v
```

Expected: fail because Today writes do not trigger experiment exposure sync.

### Task 2: Implement Deterministic Experiment-Day Sync

**Files:**
- Create: `backend/app/services/experiment_exposure_sync.py`
- Modify: `backend/app/infra/database.py`

- [ ] **Step 1: Add minimal database helpers for replace-by-day semantics**

Implement helpers in `backend/app/infra/database.py` to:
- delete all exposure rows for one `experiment_id + date`
- save one derived exposure row for that same day
- keep the operation deterministic so sync replaces stale rows instead of appending duplicates

- [ ] **Step 2: Implement the sync service**

In `backend/app/services/experiment_exposure_sync.py`:
- load experiments with statuses `("active", "draft")`
- build the one-day schedule window
- collect relevant occurrences per experiment from `linked_routine_ids`
- read current card logs for the date
- derive `full`, `partial`, `missed`, or no row using the approved protocol-day rules
- write the replacement exposure rows for that date

- [ ] **Step 3: Run the sync tests and make them pass**

Run:

```bash
cd backend && uv run pytest tests/test_experiment_exposure_sync.py -v
```

Expected: pass.

### Task 3: Wire Sync Into Today Card-Log Writes

**Files:**
- Modify: `backend/app/services/today.py`
- Modify: `backend/app/domains/routines/api/today.py`

- [ ] **Step 1: Centralize the Today write path through the compatibility service**

Ensure the route write handler uses `backend/app/services/today.py` for card-log writes so there is one orchestration path for:
- domain card-log validation/write
- experiment exposure sync

- [ ] **Step 2: Trigger date-level sync after each card-log update**

In `backend/app/services/today.py`:
- keep the existing domain `upsert_today_card_log` call
- call `sync_experiment_exposures_for_date(date)` immediately after a successful write
- return the original `CardLog`

- [ ] **Step 3: Run the Today orchestration test and make it pass**

Run:

```bash
cd backend && uv run pytest tests/test_routines_today_application.py::test_today_card_logs_recompute_linked_experiment_exposure_for_the_day -v
```

Expected: pass.

### Task 4: Full Verification

**Files:**
- Verify only

- [ ] **Step 1: Run formatting/lint verification**

Run:

```bash
cd backend && uv run ruff check
```

Expected: all checks pass.

- [ ] **Step 2: Run type checking**

Run:

```bash
cd backend && uv run pyright app/ tests/
```

Expected: `0 errors`.

- [ ] **Step 3: Run full backend tests**

Run:

```bash
cd backend && uv run pytest tests/ -v
```

Expected: full suite passes.

- [ ] **Step 4: Update docs only if the public behavior or architecture description changed materially**

If needed, update:
- `README.md`
- `docs/ARCHITECTURE.md`

For this slice, skip doc churn unless the write path or route inventory needs clarification.
