# Dashboard Overview Axis-Sections Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the central dashboard overview (`/`) into a thin shell that composes self-fetching axis **section** components, starting by extracting the recovery axis into `RecoverySection`, so future axes are isolated modules instead of more lines in one 513-line file.

**Architecture:** The route page keeps only shell concerns (ingest status, freshness, Sync, empty/loading/error, the single SSE subscription) and provides a no-data "refresh" pub/sub via Svelte context. Each axis section self-fetches its own data on mount, subscribes to the bus to re-fetch on realtime/sync, and owns its own loading/error and internal hover state. This refactor adds the bus + `RecoverySection` and thins the page; the rendered overview is pixel-identical.

**Tech Stack:** SvelteKit 2, Svelte 5 (runes), TypeScript. Validation: `cd frontend && npm run check` (no frontend unit-test harness; visual verification via browser MCP).

---

## File Structure

- **Create** `frontend/src/lib/dashboard/refresh-bus.ts` — `createRefreshBus()` + `DASHBOARD_REFRESH` context key + `RefreshBus` type. No data; just a re-fetch signal.
- **Create** `frontend/src/lib/components/recovery/RecoverySection.svelte` — the whole recovery axis: self-fetches `getDashboardOverview()`, owns `overview`/`error`/`hoveredDate`, subscribes to the bus, renders the four existing recovery components.
- **Modify** `frontend/src/routes/+page.svelte` — remove `overview`/`hoveredDate` + the recovery render + the four recovery imports; add the bus (create + `setContext` + `emit` in `fetchData`); render `<RecoverySection />`; stop fetching `getDashboardOverview`.

Unchanged: `StateLine.svelte`, `RecoveryTrajectory.svelte`, `EvidenceTable.svelte`, `EvidenceSparkline.svelte`, `FlagStrip.svelte`, `+layout.svelte`, all backend, all APIs.

---

## Task 1: Refresh bus

**Files:**
- Create: `frontend/src/lib/dashboard/refresh-bus.ts`

- [ ] **Step 1: Create the bus module**

Create `frontend/src/lib/dashboard/refresh-bus.ts` with exactly:

```ts
/**
 * Dashboard refresh signal.
 *
 * A no-data pub/sub the overview shell uses to tell self-fetching axis sections
 * "the underlying data changed — re-fetch yourself" (on realtime SSE updates or a
 * manual Sync). The shell creates one bus and provides it via context; each axis
 * section subscribes its own reload. Nothing flows through this but the signal.
 */

export type RefreshBus = {
	/** Register a reload callback; returns an unsubscribe function. */
	subscribe: (cb: () => void) => () => void;
	/** Notify all current subscribers that data changed. */
	emit: () => void;
};

/** Context key under which the overview shell provides its {@link RefreshBus}. */
export const DASHBOARD_REFRESH = Symbol('dashboard-refresh');

export function createRefreshBus(): RefreshBus {
	const subscribers = new Set<() => void>();
	return {
		subscribe(cb) {
			subscribers.add(cb);
			return () => {
				subscribers.delete(cb);
			};
		},
		emit() {
			for (const cb of subscribers) cb();
		}
	};
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run check`
Expected: 0 errors, 0 warnings.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/dashboard/refresh-bus.ts
git commit -m "Add dashboard refresh bus (no-data re-fetch signal)"
```

---

## Task 2: RecoverySection component

**Files:**
- Create: `frontend/src/lib/components/recovery/RecoverySection.svelte`

This moves the recovery render out of the page and makes it self-fetching. The four child components and their props are exactly as the page renders them today (see `+page.svelte` lines 196–216, pre-refactor).

- [ ] **Step 1: Create the section component**

Create `frontend/src/lib/components/recovery/RecoverySection.svelte` with exactly:

```svelte
<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { api, type DashboardOverview } from '$lib/api';
	import { DASHBOARD_REFRESH, type RefreshBus } from '$lib/dashboard/refresh-bus';
	import StateLine from './StateLine.svelte';
	import RecoveryTrajectory from './RecoveryTrajectory.svelte';
	import EvidenceTable from './EvidenceTable.svelte';
	import FlagStrip from './FlagStrip.svelte';

	// getContext must run during component init (not inside onMount). The shell always
	// provides the bus; `?.` guards the (unsupported) case of mounting outside the shell.
	const bus = getContext<RefreshBus | undefined>(DASHBOARD_REFRESH);

	let overview = $state<DashboardOverview | null>(null);
	let error = $state<string | null>(null);
	let hoveredDate = $state<string | null>(null);

	async function load(): Promise<void> {
		try {
			overview = await api.getDashboardOverview();
			hoveredDate = null; // drop any brushed day when the data reloads
			error = null;
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : String(e);
		}
	}

	onMount(() => {
		void load();
		return bus?.subscribe(() => void load());
	});
</script>

{#if error}
	<div class="section-error">Error: {error}</div>
{:else if !overview}
	<div class="section-loading">
		<div class="loading-pulse"></div>
		<span>Loading recovery…</span>
	</div>
{:else}
	<StateLine state={overview.state} date={overview.date} />
	<RecoveryTrajectory
		score={overview.score}
		change={overview.change}
		events={overview.events}
		onHoverDate={(d) => (hoveredDate = d)}
	/>
	<EvidenceTable
		evidence={overview.evidence}
		driverSeries={overview.driver_series}
		dates={overview.score.map((p) => p.date)}
		{hoveredDate}
	/>
	<FlagStrip
		flags={overview.flags}
		flagSeries={overview.flag_series}
		latestDate={overview.date}
		{hoveredDate}
	/>
{/if}

<style>
	.section-error {
		margin: 24px 0;
		padding: 16px;
		border: 1px solid rgba(232, 93, 74, 0.3);
		border-radius: 8px;
		background: rgba(232, 93, 74, 0.08);
		color: #e85d4a;
		font-family: 'DM Mono', monospace;
		font-size: 13px;
	}

	.section-loading {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 12px;
		height: 40vh;
		font-family: 'DM Mono', monospace;
		font-size: 13px;
		color: #5e7282;
	}

	.loading-pulse {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: #5bb5a6;
		animation: pulse 1.5s ease-in-out infinite;
	}

	@keyframes pulse {
		0%,
		100% {
			opacity: 0.3;
			transform: scale(0.8);
		}
		50% {
			opacity: 1;
			transform: scale(1.2);
		}
	}
</style>
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npm run check`
Expected: 0 errors, 0 warnings.

> Note: `npm run check` may report `RecoverySection` as unused until Task 3 imports it — that is fine; it is not an error/warning. If svelte-check flags the unused export, ignore until Task 3.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/components/recovery/RecoverySection.svelte
git commit -m "Add self-fetching RecoverySection for the recovery axis"
```

---

## Task 3: Thin the page into a shell

**Files:**
- Modify: `frontend/src/routes/+page.svelte`

The page currently fetches both daily aggregates and the dashboard overview, holds `overview`/`hoveredDate`, and renders the four recovery components inline. After this task it fetches only daily aggregates (for freshness), provides the refresh bus, emits on data update, and renders `<RecoverySection />`.

- [ ] **Step 1: Replace the imports block**

In `frontend/src/routes/+page.svelte`, replace the current import block (lines 1–15, from `<script lang="ts">` through the `FlagStrip` import) with:

```svelte
<script lang="ts">
	import { onMount, setContext } from 'svelte';
	import {
		api,
		type DailyAggregates,
		type IngestStatus,
		type SyncResult
	} from '$lib/api';
	import { startRealtimePage } from '$lib/realtime-page';
	import { calendarDayDiff, localDateIso, parseIsoDate, fmtFullDate } from '$lib/date';
	import { createRefreshBus, DASHBOARD_REFRESH } from '$lib/dashboard/refresh-bus';
	import RecoverySection from '$lib/components/recovery/RecoverySection.svelte';
```

(Removes the `DashboardOverview` type and the four recovery-component imports; adds `setContext`, the refresh bus, and `RecoverySection`.)

- [ ] **Step 2: Replace the state + bus setup**

Replace the current state declarations (lines 17–24, `let data ...` through `let hoveredDate ...`) with:

```svelte
	let data: DailyAggregates | null = $state(null);
	let ingestStatus: IngestStatus | null = $state(null);
	let emptyState: IngestStatus | null = $state(null);
	let error: string | null = $state(null);
	let syncing = $state(false);
	let syncResult = $state<SyncResult | null>(null);

	// One refresh bus for the whole overview; axis sections subscribe to re-fetch on
	// realtime/sync. setContext must run during component init (here), not in onMount.
	const bus = createRefreshBus();
	setContext(DASHBOARD_REFRESH, bus);
```

(Removes `overview` and `hoveredDate`; adds the bus + context.)

- [ ] **Step 3: Replace `fetchData`**

Replace the current `fetchData` (lines 26–44) with:

```svelte
	async function fetchData() {
		error = null;
		const status = await api.getIngestStatus();
		ingestStatus = status;
		if (status.days_in_db === 0) {
			data = null;
			emptyState = status;
			return;
		}
		data = await api.getDailyAggregates();
		emptyState = null;
		bus.emit(); // tell mounted axis sections the data changed
	}
```

(No longer fetches `getDashboardOverview`; emits the refresh signal instead of resetting `hoveredDate`.)

- [ ] **Step 4: Replace the recovery render block**

In the template, replace the entire recovery block (pre-refactor lines 196–216, the `{#if overview} … {/if}` containing `StateLine`/`RecoveryTrajectory`/`EvidenceTable`/`FlagStrip`) with a single line:

```svelte
		<RecoverySection />
```

Leave everything else in that `{:else}` branch (the `freshnessNotice` banner, the `sync-bar`, and the `sync-result-banner`) exactly as-is. Leave the `error` / `emptyState` / `!data` branches, `freshnessNotice`, `handleSync`, `formatBannerDate`, `latestIngestedDate`, `onMount`, and all `<style>` unchanged.

- [ ] **Step 5: Type-check**

Run: `cd frontend && npm run check`
Expected: 0 errors, 0 warnings. (If it reports `data`, `fmtFullDate`, `parseIsoDate`, `calendarDayDiff`, or `localDateIso` as unused, something in Steps 1–4 was over-deleted — they are all still used by `freshnessNotice`/`formatBannerDate`/the loading gate; restore as needed.)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routes/+page.svelte
git commit -m "Thin overview page into a shell that composes RecoverySection"
```

---

## Task 4: Visual verification (non-negotiable)

**Files:** none (verification only). Requires the dev servers running (`backend` on :8000, `frontend` on :5173).

- [ ] **Step 1: Type-check the whole frontend once more**

Run: `cd frontend && npm run check`
Expected: 0 errors, 0 warnings.

- [ ] **Step 2: Desktop — populated overview is unchanged**

With browser MCP: navigate to `http://localhost:5173`, resize to 1440×900. Screenshot the trajectory canvas and the evidence table. Verify the overview is visually identical to before the refactor: state line, recovery trajectory (average line + typical band + tooltip spread on hover), evidence table (wide neutral sparklines, semantic Δz), flag strip. No layout shift, no missing section.

- [ ] **Step 3: Hover-brushing still works (state lives in the section)**

Hover a point on the trajectory; confirm the evidence table + flag strip re-point to that hovered day (this proves `hoveredDate` is still correctly wired inside `RecoverySection`). Move the mouse off; confirm they return to the latest day.

- [ ] **Step 4: Realtime/sync refresh path (proves the bus)**

Click the **Sync Garmin** button (compact sync bar or freshness banner). Confirm: no console errors; after the sync completes the recovery section is still present and shows data (it re-fetched via `fetchData → bus.emit() → RecoverySection.load()`). If a stale/pending freshness banner is showing, confirm the Sync button there also works.

- [ ] **Step 5: Loading + section-error states**

- Loading: hard-reload the page; confirm the shell loader (`Mapping terrain data…`) appears, then the section briefly shows `Loading recovery…`, then content — no flash of broken layout.
- Section error: temporarily confirm graceful failure — e.g. in browser devtools, block the `GET /api/dashboard` request and reload; confirm the recovery section shows its inline `Error: …` box **without** blanking the shell (freshness/sync chrome still renders). Unblock and reload to restore.

- [ ] **Step 6: Mobile**

Resize to 390×844; screenshot the full page. Confirm the overview renders correctly (chart + table stacked, sparkline column hidden, text fits), identical to pre-refactor behavior.

- [ ] **Step 7: (No commit)**

Verification only — nothing to commit unless a defect was found and fixed (in which case commit the fix with a clear message).

---

## Self-Review Notes

- **Spec coverage:** Refresh bus → Task 1. RecoverySection (self-fetch, own loading/error, own hover, bus subscribe, `getContext` at init) → Task 2. Shell (drop `overview`/`hoveredDate`, keep `data`/freshness/sync/empty, create+provide bus, emit in `fetchData`, render `<RecoverySection/>`) → Task 3. Testing (`npm run check` + every state, hover-brushing, realtime/sync, no visual change, mobile) → Task 4. Section-local error (one axis failing doesn't blank the dashboard) → Task 2 component + Task 4 Step 5.
- **No-visual-change guarantee:** Task 2 renders the four components with byte-identical props to the pre-refactor page; Task 3 only relocates the render and the overview fetch. Verified in Task 4 Step 2 / Step 6.
- **Type consistency:** `RefreshBus`/`createRefreshBus`/`DASHBOARD_REFRESH` defined in Task 1 are imported with those exact names in Tasks 2 (`getContext<RefreshBus>`, `DASHBOARD_REFRESH`) and 3 (`createRefreshBus`, `DASHBOARD_REFRESH`). `api.getDashboardOverview()`/`getDailyAggregates()`/`getIngestStatus()`/`triggerSync()` and the `DashboardOverview`/`DailyAggregates`/`IngestStatus`/`SyncResult` types match the existing `$lib/api` surface used by the pre-refactor page.
- **Leak guard:** Task 2's `onMount` returns `bus?.subscribe(...)`, so Svelte unsubscribes on teardown — no subscriber accumulation across navigations.
