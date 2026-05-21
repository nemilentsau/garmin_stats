# Frontend Metrics Refactor Clean Slate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Guide the next frontend metrics refactor from the current post-shell-cleanup baseline without re-tracking completed UI-DRY work.

**Architecture:** Keep the frontend display-only. Review metric semantics and backend/frontend ownership before changing heavy metric pages. Make future refactors contract-backed, visually verified, and scoped to one behavior slice at a time.

**Tech Stack:** Svelte 5, SvelteKit, TypeScript, Chart.js, Tailwind utility classes, Vite, FastAPI/Pydantic-generated API contracts.

---

## Current Decisions

- The completed shell/color cleanup is no longer tracked in this plan.
- General pre-analytics cleanup is no longer tracked here: the API client uses shared request helpers, and Today/Schedule share routine card payload helpers.
- Do not structurally refactor `heart-rate`, `hrv`, or dashboard/overview pages before the analytics-agent review.
- Keep chart dataset semantics local on heavy metric pages until the analytics review decides what those pages should show.
- Do not move statistical computation, smoothing, period aggregation, exposure logic, or data transformations into the frontend.
- Do not hand-edit `frontend/src/lib/api-types.ts`; regenerate API types after backend schema changes.
- All future frontend changes must pass `cd frontend && npm run check` and visual verification in the running app.

## Remaining Work

### Task 1: Analytics-Agent Review Of Heavy Metric Pages

**Files to inspect:**
- `frontend/src/routes/heart-rate/+page.svelte`
- `frontend/src/routes/hrv/+page.svelte`
- `frontend/src/routes/+page.svelte`
- `backend/app/domains/garmin_analytics/domain/analysis/heart_rate.py`
- `backend/app/domains/garmin_analytics/domain/analysis/hrv.py`
- `backend/app/domains/garmin_analytics/domain/insights/heart_rate.py`
- `backend/app/domains/garmin_analytics/domain/insights/hrv.py`
- `backend/app/domains/garmin_analytics/contracts.py`
- `frontend/src/lib/api-types.ts`

- [ ] **Step 1: Inventory current heavy-page frontend transformations**

Run:

```bash
rg -n "map\\(|filter\\(|reduce\\(|sort\\(|ma7|avg|median|baseline|percentile|score|insight|status|trend|boxplot|week" frontend/src/routes/heart-rate frontend/src/routes/hrv frontend/src/routes/+page.svelte
```

Expected: produce a short note that classifies each match as display formatting, chart-shape adaptation, or derived metric logic.

- [ ] **Step 2: Inventory backend analytics already available**

Run:

```bash
rg -n "HeartRate|Hrv|trend|boxplot|baseline|recovery|insight|status|week|day_of_week" backend/app/domains/garmin_analytics backend/app/domains/garmin_health/contracts
```

Expected: produce a short note listing the backend fields already available for the heavy pages and the missing fields that force frontend derivation.

- [ ] **Step 3: Decide ownership for each heavy-page behavior**

Create a decision table with these columns:

```text
Page | Behavior | Current owner | Correct owner | Needed API change | Frontend change
```

Expected: every current heavy-page derived value or interaction is assigned to either backend analytics, frontend display formatting, or deliberate local chart adaptation.

- [ ] **Step 4: Choose the first implementation slice**

Pick exactly one slice:

```text
heart-rate analytics contract
hrv analytics contract
overview/dashboard analytics contract
shared history UI after analytics contracts
```

Expected: the chosen slice has clear files, expected API contract changes, tests, frontend visual checks, and no dependency on unfinished slices.

### Task 2: Write The Slice-Specific Implementation Plan

**Files to create or modify:**
- Create one new plan under `docs/superpowers/plans/` using the current date and selected slice name.

- [ ] **Step 1: Create the focused plan**

Use this filename pattern:

```text
docs/superpowers/plans/YYYY-MM-DD-<selected-heavy-metric-slice>.md
```

Expected: the new plan contains only the chosen slice, not the entire frontend refactor.

- [ ] **Step 2: Include backend tests before implementation when API behavior changes**

If the selected slice changes backend analytics or contracts, include exact backend test files and commands:

```bash
cd backend && uv run pytest tests/ -v
cd backend && uv run ruff check
cd backend && uv run pyright app/ tests/
bash scripts/generate-api-types.sh
cd frontend && npm run check
```

Expected: the plan makes the API-types flow explicit and never asks the frontend to compute analytics.

- [ ] **Step 3: Include frontend validation and visual verification**

For any selected slice with frontend changes, include:

```bash
cd frontend && npm run check
cd frontend && npm test
```

Expected: the plan names the exact routes to inspect in the browser and the interactions to exercise.

## Completion Criteria

This clean-slate plan is complete when:

- The analytics-agent review has produced the ownership decision table.
- One heavy metric-page implementation slice has a focused follow-up plan.
- Any backend schema change plan includes API type regeneration.
- Any frontend change plan includes `npm run check`, `npm test`, and browser visual verification.
- No task in this file asks to redo completed shell/color or general pre-analytics cleanup.
