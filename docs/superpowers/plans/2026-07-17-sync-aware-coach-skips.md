# Sync-Aware Coach Skips Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent Coach from declaring a missed run until Garmin activity sync has fully checked the date, and make a later run supersede any earlier skip review for the same occurrence.

**Architecture:** Garmin Sync owns a durable per-date coverage table and an adapter exposed through a narrow protocol. Bootstrap injects its read method into Coach. Coach gates only skip candidates on coverage, while its repository records and filters durable supersession when a run review conflicts with a skip.

**Tech Stack:** Python 3.13, Pydantic, SQLite/JSON1, pytest, Ruff, Pyright, uv

---

## File map

- Create `backend/app/domains/garmin_sync/infra/activity_coverage.py`: SQLite coverage adapter.
- Modify `backend/app/domains/garmin_sync/schema.py`: coverage table ownership.
- Modify `backend/app/domains/garmin_sync/dependencies.py`: coverage protocol and dependency.
- Modify `backend/app/domains/garmin_sync/infra/factory.py`: production coverage wiring.
- Modify `backend/app/domains/garmin_sync/workflows.py`: per-date complete/incomplete coverage writes.
- Modify `backend/app/bootstrap/container.py`: inject the coverage reader into Coach.
- Modify `backend/app/domains/coach/application/jobs.py`: gate skip candidates on coverage.
- Modify `backend/app/domains/coach/contracts.py`: durable supersession field.
- Modify `backend/app/domains/coach/adapters.py`: supersede conflicts and exclude them from canonical reads.
- Modify relevant backend tests and `docs/reference/data-and-ingest.md`.

### Task 1: Persist complete activity-sync coverage

**Files:**
- Create: `backend/app/domains/garmin_sync/infra/activity_coverage.py`
- Modify: `backend/app/domains/garmin_sync/schema.py`
- Modify: `backend/app/domains/garmin_sync/dependencies.py`
- Modify: `backend/app/domains/garmin_sync/infra/factory.py`
- Test: `backend/tests/domains/garmin_sync/test_ingest_application.py`

- [ ] **Step 1: Write failing coverage tests**

Add a fake coverage store to the workflow fixture and assert that an all-success sweep records all dates, while listing, payload, and storage failures leave their dates uncovered. Assert a second successful run replaces the incomplete state and unchanged successful runs remain idempotently covered.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `cd backend && uv run pytest tests/domains/garmin_sync/test_ingest_application.py -k coverage -v`

Expected: failures because `GarminSyncDependencies` has no coverage port and the workflow records no coverage.

- [ ] **Step 3: Implement the minimal coverage owner and workflow**

Define this port:

```python
class ActivitySyncCoverage(Protocol):
    def mark_covered(self, day: date) -> None: ...
    def mark_incomplete(self, day: date) -> None: ...
    def is_covered(self, day_iso: str) -> bool: ...
```

Create `activity_sync_coverage(date TEXT PRIMARY KEY, covered_at TEXT NOT NULL)`. The SQLite adapter upserts on `mark_covered`, deletes on `mark_incomplete`, and uses `SELECT 1` for `is_covered`. In `_sync_activities`, mark each day incomplete before listing and mark it covered only if listing and every required payload/store operation succeeds.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `cd backend && uv run pytest tests/domains/garmin_sync/test_ingest_application.py -v`

Expected: all workflow tests pass.

### Task 2: Gate Coach skip inference on coverage

**Files:**
- Modify: `backend/app/bootstrap/container.py`
- Modify: `backend/app/domains/coach/application/jobs.py`
- Test: `backend/tests/domains/coach/test_coach_jobs.py`
- Test: `backend/tests/bootstrap/test_container.py`

- [ ] **Step 1: Write failing Coach eligibility tests**

Create a past running card and assert no skip is enqueued when `activity_date_covered` returns false, a skip is enqueued when it returns true, and a repeated covered reconciliation creates no duplicate.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `cd backend && uv run pytest tests/domains/coach/test_coach_jobs.py tests/bootstrap/test_container.py -v`

Expected: the uncovered-date test fails because Coach currently treats every past date as eligible.

- [ ] **Step 3: Implement the coverage gate and wiring**

Add an injected `Callable[[str], bool]` to `CoachJobs`, defaulting to false for safe isolated construction. Require it in the skip branch:

```python
if day < today and self.activity_date_covered(day.isoformat()):
    ...
```

Create one `SqliteActivitySyncCoverage` in bootstrap, pass it to Garmin Sync, and inject `coverage.is_covered` into Coach.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `cd backend && uv run pytest tests/domains/coach/test_coach_jobs.py tests/bootstrap/test_container.py -v`

Expected: all tests pass.

### Task 3: Supersede conflicting skip reviews

**Files:**
- Modify: `backend/app/domains/coach/contracts.py`
- Modify: `backend/app/domains/coach/adapters.py`
- Test: `backend/tests/domains/coach/test_coach_repository.py`
- Test: `backend/tests/domains/coach/test_coach_jobs.py`

- [ ] **Step 1: Write failing repository tests**

Enqueue a skip followed by a matching run. Assert the skip has `superseded_by_review_id` set to the run review, review history contains only the run, and repeated run enqueue repairs an existing conflict without creating a job. Add the inverse ordering test so an existing run prevents a canonical skip. Add a completed superseded assessment and assert latest-measurement lookup ignores it.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `cd backend && uv run pytest tests/domains/coach/test_coach_repository.py -k 'supersed or matching_run' -v`

Expected: failures because reviews have no supersession field and canonical reads include the skip.

- [ ] **Step 3: Implement transactional supersession**

Add `superseded_by_review_id: str | None = None` to `CoachReview`. In `enqueue_run_review`, after creating or finding the run, update matching skip blobs in the same transaction. In `enqueue_skip_review`, return the existing matching run/job with `created=False` if it already exists. Add `json_extract(data, '$.superseded_by_review_id') IS NULL` to review-history and review-side measurement queries.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `cd backend && uv run pytest tests/domains/coach/test_coach_repository.py tests/domains/coach/test_coach_jobs.py -v`

Expected: all tests pass, including repeat-call idempotence.

### Task 4: Document and verify the complete contract

**Files:**
- Modify: `docs/reference/data-and-ingest.md`

- [ ] **Step 1: Update the ingest reference**

Document that only a complete per-date activity sweep records coverage, startup ingest does not, Coach skip reconciliation consumes that coverage, and late runs supersede skips.

- [ ] **Step 2: Run backend quality gates**

Run:

```bash
cd backend
uv run ruff check .
uv run pyright app/ tests/
uv run pytest tests/ -v
```

Expected: all commands exit zero.

- [ ] **Step 3: Run a read-only realistic smoke check**

Against a temporary copy of the live SQLite database, initialize the new schema, run reconciliation twice with the real read gateway and coverage adapter, and verify: no new skip is inferred for an uncovered date; the existing July 16 skip becomes superseded by its run; the second pass is a no-op. Do not mutate `storage/garmin_stats.db`.

- [ ] **Step 4: Review the diff**

Run: `git diff --check && git status --short && git diff --stat`

Expected: no whitespace errors and only scoped source, test, and documentation changes.

