# Dashboard Overview — Axis Sections Refactor — Design

**Date:** 2026-06-14
**Branch:** `dashboard-overview-sections`
**Scope:** Frontend only — the central dashboard overview route (`/`, `frontend/src/routes/+page.svelte`) and the recovery axis components under `frontend/src/lib/components/recovery/`.

## Motivation

The overview at `/` is a single 513-line `+page.svelte` that mixes two unrelated jobs:

1. **Shell concerns** — ingest status, the data-freshness banner, the Sync button + `handleSync`, the empty-state walkthrough, top-level error/loading, and the single realtime (SSE) subscription.
2. **The recovery axis** — composing `StateLine` + `RecoveryTrajectory` + `EvidenceTable` + `FlagStrip` from the `overview` payload, threaded with `hoveredDate` hover-brushing.

Today there is exactly **one** axis. The central-dashboard roadmap (`docs/central-dashboard-readiness.md`) calls for additional independent lanes (sleep opportunity, health exceptions as a lane, load, adaptation, experiment adherence). Under the current shape, each new axis would add another fetch + another block of markup to this one file, so it grows without bound. This refactor establishes a **section pattern** so each axis is an isolated module and the page becomes a thin composition shell.

## Goals / Non-Goals

**Goals**
- The route page becomes a **shell** that owns only cross-axis concerns and composes axis **section** components.
- The recovery axis is extracted into a single self-contained `RecoverySection` that owns its own data fetch, loading/error, and hover state.
- Adding a future axis requires **one new section component + one line in the page**, touching nothing in the shell.

**Non-Goals**
- No new axes are built in this effort (pattern only).
- **No visual change** — the rendered overview is pixel-identical (same components, order, styles).
- No URL change (stays `/`), no nav change, no backend change, no API/contract change.
- No cross-axis "global day cursor" — hover-brushing stays internal to the recovery axis. (Possible future idea, explicitly out of scope.)

## Decisions (from brainstorming)

- **Route:** keep the overview at `/`; decompose components only. The metric pages (`/hrv`, `/sleep`, …) are already sibling sub-tabs of the "Dashboard" section in `+layout.svelte`; no routing change is needed.
- **Data ownership:** **sections self-fetch.** Each axis section owns its own API call(s) and its own loading/error UI. The shell broadcasts a "data changed, re-fetch" signal on realtime/sync; sections subscribe and re-fetch. This keeps the shell unchanged as axes are added.
- **Section location:** `RecoverySection.svelte` lives in `lib/components/recovery/` alongside its sub-components, so that folder is the whole recovery-axis module. Future axes get sibling folders (e.g. `lib/components/sleep-opportunity/`).

## Current behavior to preserve (read from `+page.svelte`)

- **States:** `error` → error box; `emptyState` (when `ingestStatus.days_in_db === 0`) → the welcome + 3-step walkthrough; `!data` → the "Mapping terrain data…" loader; else → freshness banner / sync bar, then the recovery content.
- **Freshness:** `freshnessNotice` derives from `ingestStatus` + the latest ingested date in `data` (daily aggregates) and laptop date; renders a `stale`/`pending` banner with an inline Sync button, otherwise a compact sync bar.
- **Sync:** `handleSync` calls `api.triggerSync()` then re-fetches; shows a `syncResult` count.
- **Realtime:** `onMount` → `startRealtimePage({ fetchData, setError, setLoading })`, which fetches once and subscribes to SSE (`createDataUpdateListener(fetchData)`), returning an unsubscribe. On each SSE event `fetchData` re-runs and `hoveredDate` is reset.
- **Recovery render:** `StateLine(state, date)`, `RecoveryTrajectory(score, change, events, onHoverDate)`, `EvidenceTable(evidence, driver_series, dates, hoveredDate)`, `FlagStrip(flags, flag_series, latestDate, hoveredDate)`. `hoveredDate` is set by the trajectory and consumed by the table + flags.

> Note: the recovery render uses only `overview`. `data` (daily aggregates) is used solely for the freshness/loading shell. So the recovery fetch (`api.getDashboardOverview()`) can move into the section cleanly, while the shell keeps fetching `data` for freshness.

## Target structure

```
src/routes/+page.svelte                       SHELL only
src/lib/dashboard/refresh-bus.ts              NEW: refresh pub/sub + context key
src/lib/components/recovery/
    RecoverySection.svelte                     NEW: the recovery axis (data + hover + layout)
    StateLine.svelte                           unchanged
    RecoveryTrajectory.svelte                  unchanged
    EvidenceTable.svelte                       unchanged
    EvidenceSparkline.svelte                   unchanged
    FlagStrip.svelte                           unchanged
```

## Components

### 1. Refresh bus — `src/lib/dashboard/refresh-bus.ts`

A minimal typed pub/sub carrying **no data** — just a "re-fetch yourself" signal.

```ts
export type RefreshBus = {
	subscribe: (cb: () => void) => () => void; // returns unsubscribe
	emit: () => void;
};

export const DASHBOARD_REFRESH = Symbol('dashboard-refresh');

export function createRefreshBus(): RefreshBus {
	const subscribers = new Set<() => void>();
	return {
		subscribe(cb) {
			subscribers.add(cb);
			return () => subscribers.delete(cb);
		},
		emit() {
			for (const cb of subscribers) cb();
		}
	};
}
```

- The shell creates one bus, provides it via `setContext(DASHBOARD_REFRESH, bus)`, and `emit()`s whenever its realtime/sync flow observes a data update.
- Sections `getContext(DASHBOARD_REFRESH)`, `subscribe(theirFetch)` on mount, and unsubscribe on teardown.
- Rationale for an explicit callback bus over a reactive `$effect`-on-counter: data-fetching as an explicit subscription is clearer and easier to verify than an effect that re-runs on a tracked counter; no hidden reactive dependencies.

### 2. Shell — `src/routes/+page.svelte`

Keeps only non-axis concerns and the composition:

- **State it keeps:** `ingestStatus`, `data` (daily aggregates, for freshness), `emptyState`, `error`, `syncing`, `syncResult`. **Removes** `overview` and `hoveredDate` (both move into `RecoverySection`).
- **`fetchData` (shell version):** fetch ingest status; if `days_in_db === 0` set `emptyState` and return; else fetch `api.getDailyAggregates()` into `data`, clear `emptyState`, and `bus.emit()` so mounted sections re-fetch. (No longer fetches `getDashboardOverview`.)
- **Realtime:** unchanged `onMount(() => startRealtimePage({ fetchData, setError, setLoading: () => {} }))`.
- **Sync:** `handleSync` unchanged except it relies on `fetchData` (which now emits) to refresh sections.
- **Context:** `const bus = createRefreshBus(); setContext(DASHBOARD_REFRESH, bus);` at top of script.
- **Markup:** identical error / empty / loading / freshness / sync blocks (and their CSS stay in the shell). The recovery block (`{#if overview} … {/if}`) is replaced by `<RecoverySection />`. The shell renders `<RecoverySection />` whenever it is past the empty/loading gate (i.e. data is present).
- **CSS:** the recovery-specific markup carried no recovery-only CSS (the four components are self-styled), so all existing shell CSS stays; nothing recovery-specific needs to move.

### 3. RecoverySection — `src/lib/components/recovery/RecoverySection.svelte`

Owns the entire recovery axis:

- **State:** `overview: DashboardOverview | null`, `error: string | null`, `hoveredDate: string | null`.
- **`load()`:** `overview = await api.getDashboardOverview()`; on error set local `error`; reset `hoveredDate` on (re)load to drop a stale brushed day (mirrors the current `hoveredDate = null` on reload).
- **Lifecycle:** `getContext(DASHBOARD_REFRESH)` is read **during component init** (top of `<script>`), because Svelte requires `getContext`/`setContext` to run synchronously during initialization — not inside `onMount`. Then `onMount(() => { void load(); return bus?.subscribe(() => void load()); })` loads once and subscribes, returning the unsubscribe for teardown.
- **Render:** its own small loading placeholder until first `overview` resolves, an inline error if `load` fails, else the four components exactly as today:
  - `StateLine(state, date)`
  - `RecoveryTrajectory(score, change, events, onHoverDate=(d)=>hoveredDate=d)`
  - `EvidenceTable(evidence, driver_series, dates=score.map(p=>p.date), hoveredDate)`
  - `FlagStrip(flags, flag_series, latestDate=date, hoveredDate)`

## Data flow

```
SSE event / Sync ──> shell.fetchData() ──> refresh shell `data` (freshness) ──> bus.emit()
                                                                                   │
RecoverySection.onMount ── subscribe(load) ───────────────────────────────────────┤
                          load() once on mount                                     ▼
                                                              RecoverySection.load() re-fetches overview
```

First paint: shell fetches ingest status + `data`; once past the empty/loading gate it renders `<RecoverySection/>`, which self-loads `overview` on mount. Subsequent SSE/sync: shell refreshes freshness and emits; the section re-fetches. No `bus.emit()` is required for the section's first load (it self-loads on mount).

## Error handling

- **Shell errors** (ingest status / daily aggregates / sync) keep the existing top-level `error` box.
- **Section errors** (overview fetch) are local to `RecoverySection` — a compact inline error inside the section, so one axis failing never blanks the whole dashboard (a property that matters more as axes multiply). This is a deliberate, small improvement consistent with the self-fetch model.

## Testing

No frontend unit harness exists in this project (validation is `npm run check` + visual). Test plan:

- `cd frontend && npm run check` → 0 errors.
- Browser-MCP visual verification at desktop (1440) and mobile (390), confirming **no visual change** and every state:
  - **Empty** (simulate / observe `days_in_db === 0` path) → walkthrough renders.
  - **Loading** → shell loader, then section loader, then content.
  - **Populated overview** → identical to pre-refactor (state line, trajectory, evidence, flags).
  - **Hover-brushing** → hovering the trajectory still repoints the evidence table + flag strip to that day (proves hover state still wired inside the section).
  - **Freshness + Sync** → banner/sync bar render; clicking Sync refreshes.
  - **Realtime/sync refresh** → after a data update, the recovery section re-fetches and updates (proves the bus works). If SSE can't be triggered in the harness, verify via the Sync path (which routes through `fetchData` → `emit`).

## Risks / Open items

- **Double-subscription / leak:** the section must return its `unsubscribe` from `onMount` so re-mounts don't accumulate subscribers. Covered in the section lifecycle above; verify no duplicate fetches on navigation away/back.
- **First-load ordering:** the section self-loads on mount, independent of the shell's emit — so there is no race where the section misses the initial data. The shell only needs to gate empty/loading before mounting the section.
- **`getContext` outside a shell:** `RecoverySection` assumes it is rendered under the shell that provides `DASHBOARD_REFRESH`. It is only ever mounted by the shell, so this holds; the plan should still guard `getContext` returning undefined defensively (no-op subscribe) to avoid a hard crash if reused elsewhere.
