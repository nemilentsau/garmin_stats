# Frontend UI DRY Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce duplicated Svelte page, chart, and routine-card code while preserving every existing route, API call, chart, interaction, and visible behavior.

**Architecture:** Extract only repeated UI plumbing and configuration builders into shared frontend modules. Keep metric-specific data selection inside each route so the frontend remains display-only and does not gain statistical or aggregation ownership. Migrate pages in small waves, validating TypeScript and screenshots after each wave.

**Tech Stack:** Svelte 5, SvelteKit, TypeScript, Chart.js, Tailwind utility classes, Vite.

---

## Scope

This plan covers frontend-only DRY refactors:

- Consolidate duplicate Chart.js Svelte wrapper components.
- Extract repeated metric page shell components for loading/error/header/chart-card UI.
- Extract reusable Chart.js dark-theme option helpers and metric chart config helpers.
- Migrate simple metric pages first, then pages with weekly spread charts.
- Extract shared day-strip/history panel UI from Heart Rate and HRV without changing chart data or insights.
- Extract shared routine payload types, constants, and pure payload helpers used by Today and Routine Schedule.

This plan intentionally does not:

- Change backend API routes, generated API types, or API response contracts.
- Redesign dashboard layouts, chart selection, colors, typography, or information hierarchy.
- Move statistical computation, smoothing, period aggregation, exposure logic, or data transformations into the frontend.
- Merge all metric routes into a generic metric-page engine.

## File Map

- `frontend/src/lib/components/charts/ChartCanvas.svelte`
  New generic Chart.js canvas owner. Handles mount, update, destroy, height, and optional square layout.

- `frontend/src/lib/components/LineChart.svelte`
- `frontend/src/lib/components/BarChart.svelte`
- `frontend/src/lib/components/DoughnutChart.svelte`
- `frontend/src/lib/components/PolarAreaChart.svelte`
- `frontend/src/lib/components/ScatterChart.svelte`
  Keep compatibility wrappers, but delegate to `ChartCanvas.svelte`.

- `frontend/src/lib/components/PageState.svelte`
  New shared loading/error/content shell for metric-style pages.

- `frontend/src/lib/components/MetricPageHeader.svelte`
  New shared title plus optional `TrendRangePicker` header.

- `frontend/src/lib/components/ChartCard.svelte`
  New shared chart panel chrome for repeated metric chart cards.

- `frontend/src/lib/chart-options.ts`
  New shared Chart.js option builders. Owns dark legend, metric x/y scales, time axis, tooltip wiring, and common line chart options.

- `frontend/src/lib/week.ts`
  New shared ISO week label helpers currently duplicated by Heart Rate and HRV.

- `frontend/src/lib/components/DayStrip.svelte`
  New reusable history day selector strip.

- `frontend/src/lib/components/HistoryPanel.svelte`
  New reusable expandable selected-day panel shell.

- `frontend/src/lib/routines/card-payloads.ts`
  New shared routine-card payload types, payload casts, renderer labels/icons, slot accents, and card brief helpers.

- `frontend/src/routes/skin-temp/+page.svelte`
- `frontend/src/routes/respiration/+page.svelte`
- `frontend/src/routes/pulse-ox/+page.svelte`
  First migration wave: simple daily trend plus optional intraday chart pages.

- `frontend/src/routes/stress/+page.svelte`
- `frontend/src/routes/body-battery/+page.svelte`
- `frontend/src/routes/sleep/+page.svelte`
  Second migration wave: pages with analysis trends, weekly spread charts, and intraday detail.

- `frontend/src/routes/heart-rate/+page.svelte`
- `frontend/src/routes/hrv/+page.svelte`
  Third migration wave: shared week helpers, day strip, and history panel shell.

- `frontend/src/routes/today/+page.svelte`
- `frontend/src/routes/routines/schedule/+page.svelte`
  Fourth migration wave: shared routine payload helpers and constants.

- `frontend/tests/metric-daily-api-usage.test.mjs`
  Keep existing API-usage guard unchanged. Add narrow static checks only if a refactor introduces an easy-to-regress contract.

---

## Task 1: Establish Baseline And Screenshots

**Files:**
- Modify: none

- [ ] **Step 1: Check current frontend type state**

Run:

```bash
cd frontend && npm run check
```

Expected: command exits with code `0`. If it fails before any edits, record the exact existing failures in the implementation notes and do not mix unrelated fixes into this refactor.

- [ ] **Step 2: Start the frontend dev server**

Run:

```bash
cd frontend && npm run dev -- --host 127.0.0.1
```

Expected: Vite prints a local URL, normally `http://127.0.0.1:5173/`.

- [ ] **Step 3: Capture baseline screenshots**

Use browser MCP screenshots for these routes:

```text
/
/heart-rate
/hrv
/sleep
/stress
/body-battery
/respiration
/skin-temp
/pulse-ox
/today
/routines/schedule
```

Expected: every route renders without runtime errors. Save the screenshot paths or browser MCP evidence in the work notes for later comparison.

- [ ] **Step 4: Commit the no-op baseline note if a branch workflow is being used**

If the implementation session uses commits, do not commit code yet. Record baseline command output in the task notes.

---

## Task 2: Consolidate Chart Components Behind `ChartCanvas`

**Files:**
- Create: `frontend/src/lib/components/charts/ChartCanvas.svelte`
- Modify: `frontend/src/lib/components/LineChart.svelte`
- Modify: `frontend/src/lib/components/BarChart.svelte`
- Modify: `frontend/src/lib/components/DoughnutChart.svelte`
- Modify: `frontend/src/lib/components/PolarAreaChart.svelte`
- Modify: `frontend/src/lib/components/ScatterChart.svelte`

- [ ] **Step 1: Add the generic chart canvas component**

Create `frontend/src/lib/components/charts/ChartCanvas.svelte`:

```svelte
<script lang="ts" generics="TType extends keyof import('chart.js').ChartTypeRegistry">
	import { onMount } from 'svelte';
	import { Chart } from '$lib/chart-setup';
	import type { ChartConfiguration, ChartTypeRegistry } from 'chart.js';

	let {
		config,
		type,
		height = 300,
		square = false
	}: {
		config: ChartConfiguration<TType>;
		type: TType;
		height?: number;
		square?: boolean;
	} = $props();

	let canvas: HTMLCanvasElement;
	let chart: Chart<TType> | null = null;

	onMount(() => {
		chart = new Chart(canvas, { ...config, type });
		return () => chart?.destroy();
	});

	$effect(() => {
		if (!chart) return;
		chart.data = config.data;
		if (config.options) {
			chart.options = config.options as Chart<TType>['options'];
		}
		chart.update();
	});

	const containerStyle = $derived(
		square
			? `height: ${height}px; max-width: ${height}px; margin: 0 auto; position: relative;`
			: `height: ${height}px; position: relative;`
	);
</script>

<div style={containerStyle}>
	<canvas bind:this={canvas}></canvas>
</div>
```

- [ ] **Step 2: Replace each existing chart wrapper with delegation**

Use this exact pattern, changing only the chart type.

`frontend/src/lib/components/LineChart.svelte`:

```svelte
<script lang="ts">
	import type { ChartConfiguration } from 'chart.js';
	import ChartCanvas from '$lib/components/charts/ChartCanvas.svelte';

	let { config, height = 300 }: { config: ChartConfiguration<'line'>; height?: number } = $props();
</script>

<ChartCanvas type="line" {config} {height} />
```

`frontend/src/lib/components/BarChart.svelte`:

```svelte
<script lang="ts">
	import type { ChartConfiguration } from 'chart.js';
	import ChartCanvas from '$lib/components/charts/ChartCanvas.svelte';

	let { config, height = 300 }: { config: ChartConfiguration<'bar'>; height?: number } = $props();
</script>

<ChartCanvas type="bar" {config} {height} />
```

`frontend/src/lib/components/DoughnutChart.svelte`:

```svelte
<script lang="ts">
	import type { ChartConfiguration } from 'chart.js';
	import ChartCanvas from '$lib/components/charts/ChartCanvas.svelte';

	let { config, height = 300 }: { config: ChartConfiguration<'doughnut'>; height?: number } = $props();
</script>

<ChartCanvas type="doughnut" {config} {height} />
```

`frontend/src/lib/components/PolarAreaChart.svelte`:

```svelte
<script lang="ts">
	import type { ChartConfiguration } from 'chart.js';
	import ChartCanvas from '$lib/components/charts/ChartCanvas.svelte';

	let { config, height = 300 }: { config: ChartConfiguration<'polarArea'>; height?: number } = $props();
</script>

<ChartCanvas type="polarArea" {config} {height} square />
```

`frontend/src/lib/components/ScatterChart.svelte`:

```svelte
<script lang="ts">
	import type { ChartConfiguration } from 'chart.js';
	import ChartCanvas from '$lib/components/charts/ChartCanvas.svelte';

	let { config, height = 300 }: { config: ChartConfiguration<'scatter'>; height?: number } = $props();
</script>

<ChartCanvas type="scatter" {config} {height} />
```

- [ ] **Step 3: Validate chart wrapper typing**

Run:

```bash
cd frontend && npm run check
```

Expected: command exits with code `0`.

- [ ] **Step 4: Visually verify chart rendering**

With the dev server running, inspect:

```text
/heart-rate
/hrv
/sleep
/body-battery
```

Expected: line, bar, scatter, and polar charts are visible, correctly sized, and nonblank.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/components/charts/ChartCanvas.svelte frontend/src/lib/components/LineChart.svelte frontend/src/lib/components/BarChart.svelte frontend/src/lib/components/DoughnutChart.svelte frontend/src/lib/components/PolarAreaChart.svelte frontend/src/lib/components/ScatterChart.svelte
git commit -m "refactor(frontend): consolidate chart canvas wrappers"
```

---

## Task 3: Add Shared Metric Page Shell Components

**Files:**
- Create: `frontend/src/lib/components/PageState.svelte`
- Create: `frontend/src/lib/components/MetricPageHeader.svelte`
- Create: `frontend/src/lib/components/ChartCard.svelte`

- [ ] **Step 1: Add shared loading/error/content shell**

Create `frontend/src/lib/components/PageState.svelte`:

```svelte
<script lang="ts">
	let {
		error,
		loading,
		loadingLabel = 'Loading...',
		children
	}: {
		error: string | null;
		loading: boolean;
		loadingLabel?: string;
		children: () => unknown;
	} = $props();
</script>

{#if error}
	<div class="rounded-lg border border-[rgba(232,93,74,0.3)] bg-[rgba(232,93,74,0.08)] p-4">
		<p class="text-[#E85D4A]">Error: {error}</p>
	</div>
{:else if loading}
	<div class="flex h-64 items-center justify-center">
		<div class="text-[#5e7282]">{loadingLabel}</div>
	</div>
{:else}
	{@render children()}
{/if}
```

- [ ] **Step 2: Add shared metric page header**

Create `frontend/src/lib/components/MetricPageHeader.svelte`:

```svelte
<script lang="ts">
	import TrendRangePicker from '$lib/components/TrendRangePicker.svelte';
	import type { TrendRange } from '$lib/trend-range';

	let {
		title,
		trendRange = $bindable(),
		showTrendRange = true
	}: {
		title: string;
		trendRange?: TrendRange;
		showTrendRange?: boolean;
	} = $props();
</script>

<div class="mb-4 flex items-center justify-between gap-4">
	<h1 class="text-xl font-bold text-[#e8f0f5]">{title}</h1>
	{#if showTrendRange && trendRange}
		<TrendRangePicker bind:value={trendRange} />
	{/if}
</div>
```

- [ ] **Step 3: Add shared chart card chrome**

Create `frontend/src/lib/components/ChartCard.svelte`:

```svelte
<script lang="ts">
	let {
		title,
		footnote = '',
		compact = false,
		children
	}: {
		title: string;
		footnote?: string;
		compact?: boolean;
		children: () => unknown;
	} = $props();
</script>

<div class="mb-6 rounded-lg border border-[rgba(255,255,255,0.05)] bg-[rgba(255,255,255,0.02)] p-5">
	<h2 class="mb-3 text-sm font-semibold uppercase tracking-wide text-[#8a9baa]">{title}</h2>
	{@render children()}
	{#if footnote}
		<p class="mt-2 text-xs text-[#4a5c6a]">{footnote}</p>
	{/if}
</div>
```

- [ ] **Step 4: Validate component typing**

Run:

```bash
cd frontend && npm run check
```

Expected: command exits with code `0`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/components/PageState.svelte frontend/src/lib/components/MetricPageHeader.svelte frontend/src/lib/components/ChartCard.svelte
git commit -m "refactor(frontend): add shared metric page shells"
```

---

## Task 4: Add Shared Chart Option Builders

**Files:**
- Create: `frontend/src/lib/chart-options.ts`
- Modify: `frontend/src/lib/chart-setup.ts`

- [ ] **Step 1: Add reusable chart option helpers**

Create `frontend/src/lib/chart-options.ts`:

```ts
import type { ChartConfiguration, ChartDataset } from 'chart.js';
import { chartTooltip, DARK_BORDER, DARK_GRID, DARK_GRID_Y, DARK_TICK } from '$lib/chart-setup';
import { withAlpha } from '$lib/colors';

export const darkLegend = {
	labels: { boxWidth: 12, font: { size: 11 }, color: '#8a9baa' }
} as const;

export function categoryXAxis(maxTicksLimit?: number) {
	return {
		ticks: { maxRotation: 45, font: { size: 10 }, ...DARK_TICK, ...(maxTicksLimit ? { maxTicksLimit } : {}) },
		grid: DARK_GRID,
		border: DARK_BORDER
	} as const;
}

export function timeXAxis() {
	return {
		type: 'time' as const,
		time: { unit: 'hour' as const, displayFormats: { hour: 'HH:mm' } },
		ticks: { font: { size: 10 }, ...DARK_TICK },
		grid: DARK_GRID,
		border: DARK_BORDER
	} as const;
}

export function metricYAxis(title: string, options: { beginAtZero?: boolean; min?: number; max?: number } = {}) {
	return {
		...options,
		title: { display: true, text: title, ...DARK_TICK },
		ticks: DARK_TICK,
		grid: DARK_GRID_Y,
		border: DARK_BORDER
	} as const;
}

export function darkLineOptions(args: {
	color: string;
	yTitle: string;
	beginAtZero?: boolean;
	min?: number;
	max?: number;
	xMaxTicksLimit?: number;
	showLegend?: boolean;
	timeAxis?: boolean;
}): NonNullable<ChartConfiguration<'line'>['options']> {
	return {
		responsive: true,
		maintainAspectRatio: false,
		interaction: { mode: 'index', intersect: false },
		plugins: {
			legend: args.showLegend === false ? { display: false } : darkLegend,
			tooltip: chartTooltip(withAlpha(args.color, '60'))
		},
		scales: {
			x: args.timeAxis ? timeXAxis() : categoryXAxis(args.xMaxTicksLimit),
			y: metricYAxis(args.yTitle, {
				beginAtZero: args.beginAtZero,
				min: args.min,
				max: args.max
			})
		}
	};
}

export function simpleIntradayLineConfig(args: {
	label: string;
	color: string;
	yTitle: string;
	labels: string[];
	values: Array<number | null>;
	beginAtZero?: boolean;
	min?: number;
	max?: number;
}): ChartConfiguration<'line'> | null {
	if (args.labels.length === 0 || args.values.length === 0) return null;
	return {
		type: 'line',
		data: {
			labels: args.labels,
			datasets: [
				{
					label: args.label,
					data: args.values,
					borderColor: args.color,
					borderWidth: 1.5,
					pointRadius: 0,
					tension: 0.2,
					fill: { target: 'origin', above: withAlpha(args.color, '10') }
				}
			]
		},
		options: darkLineOptions({
			color: args.color,
			yTitle: args.yTitle,
			beginAtZero: args.beginAtZero,
			min: args.min,
			max: args.max,
			showLegend: false,
			timeAxis: true
		})
	};
}

export function weeklySpreadDatasets<T>(
	boxes: T[],
	color: string,
	fields: { max: keyof T; q3: keyof T; median: keyof T; q1: keyof T; min: keyof T }
): ChartDataset<'line'>[] {
	return [
		{
			label: 'Max',
			data: boxes.map((box) => box[fields.max] as number | null),
			borderColor: withAlpha(color, '30'),
			borderWidth: 1,
			borderDash: [3, 3],
			pointRadius: 0,
			tension: 0.3,
			fill: false
		},
		{
			label: 'Q3',
			data: boxes.map((box) => box[fields.q3] as number | null),
			borderColor: withAlpha(color, '50'),
			borderWidth: 1,
			pointRadius: 0,
			tension: 0.3,
			fill: false
		},
		{
			label: 'Median',
			data: boxes.map((box) => box[fields.median] as number | null),
			borderColor: color,
			borderWidth: 2.5,
			pointRadius: 0,
			tension: 0.3,
			fill: '-1',
			backgroundColor: withAlpha(color, '15')
		},
		{
			label: 'Q1',
			data: boxes.map((box) => box[fields.q1] as number | null),
			borderColor: withAlpha(color, '50'),
			borderWidth: 1,
			pointRadius: 0,
			tension: 0.3,
			fill: '-1',
			backgroundColor: withAlpha(color, '10')
		},
		{
			label: 'Min',
			data: boxes.map((box) => box[fields.min] as number | null),
			borderColor: withAlpha(color, '30'),
			borderWidth: 1,
			borderDash: [3, 3],
			pointRadius: 0,
			tension: 0.3,
			fill: false
		}
	];
}
```

- [ ] **Step 2: Keep `chart-setup.ts` as registration-only plus constants**

Do not remove exports currently used by existing pages. `chart-options.ts` is additive in this task.

- [ ] **Step 3: Validate**

Run:

```bash
cd frontend && npm run check
```

Expected: command exits with code `0`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/chart-options.ts frontend/src/lib/chart-setup.ts
git commit -m "refactor(frontend): add shared chart option builders"
```

---

## Task 5: Migrate Simple Metric Pages

**Files:**
- Modify: `frontend/src/routes/skin-temp/+page.svelte`
- Modify: `frontend/src/routes/respiration/+page.svelte`
- Modify: `frontend/src/routes/pulse-ox/+page.svelte`

- [ ] **Step 1: Replace repeated shell imports**

In each file, add:

```ts
import PageState from '$lib/components/PageState.svelte';
import MetricPageHeader from '$lib/components/MetricPageHeader.svelte';
import ChartCard from '$lib/components/ChartCard.svelte';
```

Remove direct `TrendRangePicker` imports where the header now owns it.

- [ ] **Step 2: Replace simple intraday configs with helper where shape matches**

For `respiration` and `pulse-ox`, replace the repeated intraday `ChartConfiguration<'line'>` object with:

```ts
import { simpleIntradayLineConfig, darkLineOptions } from '$lib/chart-options';
```

Then build configs with:

```ts
let intradayConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
	if (!intradayData || intradayData.respiration.length === 0) return null;
	return simpleIntradayLineConfig({
		label: 'Respiration',
		color: COLORS.respiration,
		yTitle: 'br/min',
		labels: intradayData.respiration.map((d) => d.timestamp),
		values: intradayData.respiration.map((d) => d.value),
		beginAtZero: false
	});
});
```

For pulse ox use `label: 'SpO2'`, `color: COLORS.spo2`, `yTitle: '%'`, and `min: 85`.

- [ ] **Step 3: Replace page shell markup**

Use this page structure in each migrated route:

```svelte
<PageState {error} {loading}>
	{#if agg}
		<MetricPageHeader title="Respiration Rate" bind:trendRange />

		<!-- Keep existing MetricDefinition, DateSelector, stats grid, and chart content here. -->
	{/if}
</PageState>
```

Keep existing title strings, metric definitions, stat cards, date selectors, chart content, and footnote text exactly as rendered today.

- [ ] **Step 4: Replace chart card chrome**

Convert repeated card markup to:

```svelte
<ChartCard title="Daily Trend">
	{#if trendConfig}
		<LineChart config={trendConfig} height={300} />
	{/if}
</ChartCard>
```

For intraday cards, keep the existing title text and readings footnote:

```svelte
<ChartCard title={`Intraday — ${selectedDate}`} footnote={`${intradayData?.respiration.length ?? 0} readings`}>
	<LineChart config={intradayConfig} height={300} />
</ChartCard>
```

- [ ] **Step 5: Validate and visually inspect**

Run:

```bash
cd frontend && npm run check
```

Expected: command exits with code `0`.

Use browser MCP screenshots for:

```text
/skin-temp
/respiration
/pulse-ox
```

Expected: headers, definitions, stat cards, trend charts, date selector, selected-date intraday chart, loading state, and error styling match baseline behavior.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routes/skin-temp/+page.svelte frontend/src/routes/respiration/+page.svelte frontend/src/routes/pulse-ox/+page.svelte
git commit -m "refactor(frontend): migrate simple metric pages to shared shells"
```

---

## Task 6: Migrate Analysis Metric Pages With Weekly Spreads

**Files:**
- Modify: `frontend/src/routes/stress/+page.svelte`
- Modify: `frontend/src/routes/body-battery/+page.svelte`
- Modify: `frontend/src/routes/sleep/+page.svelte`

- [ ] **Step 1: Use shared shell components**

Repeat the `PageState`, `MetricPageHeader`, and `ChartCard` pattern from Task 5.

- [ ] **Step 2: Replace weekly spread dataset duplication**

For `stress`, replace the boxplot datasets with:

```ts
import { darkLineOptions, simpleIntradayLineConfig, weeklySpreadDatasets } from '$lib/chart-options';
```

```ts
let boxplotConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
	if (!analysis || analysis.weekly_boxplots.length === 0) return null;
	const boxes = analysis.weekly_boxplots;
	return {
		type: 'line',
		data: {
			labels: boxes.map((box) => box.iso_week),
			datasets: weeklySpreadDatasets(boxes, COLORS.stress, {
				max: 'max_avg',
				q3: 'q3_avg',
				median: 'median_avg',
				q1: 'q1_avg',
				min: 'min_avg'
			})
		},
		options: darkLineOptions({
			color: COLORS.stress,
			yTitle: 'stress',
			beginAtZero: true,
			max: 100,
			xMaxTicksLimit: 12
		})
	};
});
```

For `body-battery`, use `COLORS.bodyBattery`, `yTitle: 'battery %'`, `max: 100`, and fields `max_val`, `q3_val`, `median_val`, `q1_val`, `min_val`.

For `sleep`, use `COLORS.sleep`, `yTitle: 'score'`, and fields `max_score`, `q3_score`, `median_score`, `q1_score`, `min_score`.

- [ ] **Step 3: Replace simple intraday configs only where behavior matches**

Use `simpleIntradayLineConfig` for stress and body battery. Keep the custom sleep stage chart in the route because it has stepped stages, reversed axis, and custom tooltip labels.

- [ ] **Step 4: Keep trend dataset definitions local**

Do not create a generic trend-page abstraction for the main trend charts in this task. The dataset choices differ enough that local route code is clearer and lower risk.

- [ ] **Step 5: Validate and visually inspect**

Run:

```bash
cd frontend && npm run check
```

Expected: command exits with code `0`.

Use browser MCP screenshots for:

```text
/stress
/body-battery
/sleep
```

Expected: trend charts, weekly spread charts, date selector, selected-date intraday panels, and sleep assessment stat cards match baseline behavior.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routes/stress/+page.svelte frontend/src/routes/body-battery/+page.svelte frontend/src/routes/sleep/+page.svelte
git commit -m "refactor(frontend): migrate analysis metric pages to shared chart helpers"
```

---

## Task 7: Extract Week And History Strip Helpers For Heart Rate And HRV

**Files:**
- Create: `frontend/src/lib/week.ts`
- Create: `frontend/src/lib/components/DayStrip.svelte`
- Create: `frontend/src/lib/components/HistoryPanel.svelte`
- Modify: `frontend/src/routes/heart-rate/+page.svelte`
- Modify: `frontend/src/routes/hrv/+page.svelte`

- [ ] **Step 1: Extract duplicated ISO week helpers**

Create `frontend/src/lib/week.ts`:

```ts
export function isoWeekToMonday(isoWeek: string): Date | null {
	const match = isoWeek.match(/^(\d{4})-W(\d{2})$/);
	if (!match) return null;
	const year = Number.parseInt(match[1], 10);
	const week = Number.parseInt(match[2], 10);
	const jan4 = new Date(year, 0, 4);
	const dow = (jan4.getDay() + 6) % 7;
	const weekStart = new Date(jan4);
	weekStart.setDate(jan4.getDate() - dow + (week - 1) * 7);
	return weekStart;
}

export function fmtWeekLabel(isoWeek: string): string {
	const monday = isoWeekToMonday(isoWeek);
	if (!monday) return isoWeek;
	return monday.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}
```

- [ ] **Step 2: Add shared day strip component**

Create `frontend/src/lib/components/DayStrip.svelte`:

```svelte
<script lang="ts">
	type LegendItem = { label: string; color: string };

	let {
		days,
		selectedDate,
		colorByDate,
		legend,
		canPrev,
		canNext,
		onselect,
		onprev,
		onnext,
		onclear
	}: {
		days: string[];
		selectedDate: string;
		colorByDate: Map<string, string>;
		legend: LegendItem[];
		canPrev: boolean;
		canNext: boolean;
		onselect: (date: string) => void;
		onprev: () => void;
		onnext: () => void;
		onclear: () => void;
	} = $props();
</script>

<div class="day-nav">
	<div class="day-nav-controls">
		<button class="nav-arrow" disabled={!canPrev} onclick={onprev}>←</button>
		<button class="day-label" onclick={onclear}>{selectedDate || 'All Days'}</button>
		<button class="nav-arrow" disabled={!canNext} onclick={onnext}>→</button>
	</div>
	<div class="day-strip-container">
		<div class="day-strip">
			{#each days as day}
				<button
					class="day-cell"
					class:selected={day === selectedDate}
					style="background: {colorByDate.get(day) ?? '#3a4a5a'};"
					title={day}
					onclick={() => onselect(day === selectedDate ? '' : day)}
				></button>
			{/each}
		</div>
		<div class="day-strip-legend">
			{#each legend as item}
				<span><i class="legend-dot" style="background:{item.color};"></i>{item.label}</span>
			{/each}
		</div>
	</div>
</div>

<style>
	.day-nav { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; }
	.day-nav-controls { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
	.nav-arrow { width: 28px; height: 28px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.03); color: #8a9baa; cursor: pointer; font-size: 13px; display: flex; align-items: center; justify-content: center; transition: all 0.15s; }
	.nav-arrow:hover:not(:disabled) { background: rgba(255,255,255,0.08); color: #c8d6e0; }
	.nav-arrow:disabled { opacity: 0.3; cursor: default; }
	.day-label { font-family: 'DM Mono', monospace; font-size: 12px; color: #c8d6e0; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 4px 10px; cursor: pointer; min-width: 100px; text-align: center; }
	.day-label:hover { background: rgba(255,255,255,0.08); }
	.day-strip-container { flex: 1; overflow: hidden; }
	.day-strip { display: flex; gap: 2px; overflow-x: auto; scrollbar-width: none; padding: 2px 0; }
	.day-strip::-webkit-scrollbar { display: none; }
	.day-cell { width: 8px; min-width: 8px; height: 22px; border-radius: 2px; border: none; cursor: pointer; transition: all 0.12s; opacity: 0.7; }
	.day-cell:hover { opacity: 1; transform: scaleY(1.3); }
	.day-cell.selected { opacity: 1; outline: 2px solid #e8f0f5; outline-offset: 1px; transform: scaleY(1.4); }
	.day-strip-legend { display: flex; gap: 12px; margin-top: 4px; }
	.day-strip-legend span { font-size: 10px; color: #5e7282; display: flex; align-items: center; gap: 4px; }
	.legend-dot { display: inline-block; width: 7px; height: 7px; border-radius: 2px; }
</style>
```

- [ ] **Step 3: Add shared history panel shell**

Create `frontend/src/lib/components/HistoryPanel.svelte`:

```svelte
<script lang="ts">
	import { slide } from 'svelte/transition';

	let {
		selectedDate,
		accentColor,
		comparison,
		onclose,
		children
	}: {
		selectedDate: string;
		accentColor: string;
		comparison?: string;
		onclose: () => void;
		children: () => unknown;
	} = $props();
</script>

<div
	class="history-detail"
	style="border-color: {accentColor}26; border-left-color: {accentColor}66;"
	transition:slide={{ duration: 300 }}
>
	<div class="history-detail-header">
		<div class="history-detail-title">
			<span class="history-date">{selectedDate}</span>
			{#if comparison}
				<span class="history-comparison">{@html comparison}</span>
			{/if}
		</div>
		<button class="close-btn" onclick={onclose} title="Close">✕</button>
	</div>
	{@render children()}
</div>

<style>
	.history-detail { background: rgba(255,255,255,0.025); border: 1px solid; border-left: 3px solid; border-radius: 10px; padding: 20px; margin-bottom: 14px; }
	.history-detail-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
	.history-detail-title { display: flex; flex-direction: column; gap: 4px; }
	.history-date { font-family: 'DM Mono', monospace; font-size: 16px; font-weight: 600; color: #e8f0f5; letter-spacing: 0.5px; }
	.history-comparison { font-size: 12px; color: #8a9baa; }
	.history-comparison :global(strong) { color: #c8d6e0; }
	.close-btn { width: 28px; height: 28px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.03); color: #6b7d8e; cursor: pointer; font-size: 14px; display: flex; align-items: center; justify-content: center; transition: all 0.15s; flex-shrink: 0; }
	.close-btn:hover { background: rgba(255,255,255,0.08); color: #c8d6e0; }
</style>
```

- [ ] **Step 4: Migrate Heart Rate and HRV carefully**

In both route files:

```ts
import DayStrip from '$lib/components/DayStrip.svelte';
import HistoryPanel from '$lib/components/HistoryPanel.svelte';
import { fmtWeekLabel, isoWeekToMonday } from '$lib/week';
```

Remove local `isoWeekToMonday` and `fmtWeekLabel` functions. Replace only the day-strip markup and history outer shell. Keep metric-specific history content, insight content, chart config functions, and stat bars local.

- [ ] **Step 5: Validate and visually inspect**

Run:

```bash
cd frontend && npm run check
```

Expected: command exits with code `0`.

Use browser MCP screenshots for:

```text
/heart-rate
/hrv
```

Click a day in each history strip, verify the detail panel opens, previous/next arrows work, clearing returns to `All Days`, and all charts remain visible.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/week.ts frontend/src/lib/components/DayStrip.svelte frontend/src/lib/components/HistoryPanel.svelte frontend/src/routes/heart-rate/+page.svelte frontend/src/routes/hrv/+page.svelte
git commit -m "refactor(frontend): share metric history strip components"
```

---

## Task 8: Extract Shared Routine Card Payload Helpers

**Files:**
- Create: `frontend/src/lib/routines/card-payloads.ts`
- Modify: `frontend/src/routes/today/+page.svelte`
- Modify: `frontend/src/routes/routines/schedule/+page.svelte`

- [ ] **Step 1: Create routine payload helper module**

Create `frontend/src/lib/routines/card-payloads.ts`:

```ts
import { COLORS, withAlpha } from '$lib/colors';

export type SlotAccent = { color: string; shadow: string };

export type TimerPayload = {
	duration_minutes?: number;
	pattern?: string;
	instructions?: string;
	segments?: { label: string; duration_seconds: number }[];
	rating_prompts?: { key: string; label: string; scale_min?: number; scale_max?: number }[];
};

export type ChecklistPayload = {
	instructions?: string;
	items?: { id: string; label: string; detail?: string }[];
};

export type ExercisePayload = {
	instructions?: string;
	exercises?: {
		id: string;
		label: string;
		detail?: string;
		reps?: string;
		duration_seconds?: number;
	}[];
};

export const SLOT_ORDER = ['morning', 'midday', 'evening', 'anytime'] as const;
export type SlotName = (typeof SLOT_ORDER)[number];

export const SLOT_LABELS: Record<SlotName, string> = {
	morning: 'Morning',
	midday: 'Midday',
	evening: 'Evening',
	anytime: 'Anytime'
};

export const SLOT_ACCENTS: Record<SlotName, SlotAccent> = {
	morning: { color: COLORS.respiration, shadow: withAlpha(COLORS.respiration, '30') },
	midday: { color: COLORS.spo2, shadow: withAlpha(COLORS.spo2, '30') },
	evening: { color: COLORS.hrv, shadow: withAlpha(COLORS.hrv, '30') },
	anytime: { color: COLORS.stress, shadow: withAlpha(COLORS.stress, '30') }
};

export const SLOT_INDEX = Object.fromEntries(
	SLOT_ORDER.map((slot, index) => [slot, index])
) as Record<SlotName, number>;

export const RENDERER_ICONS: Record<string, string> = {
	exercise_block: '\u{1F4AA}',
	timer_session: '\u{23F1}',
	checklist_block: '\u{2611}'
};

export const RENDERER_LABELS: Record<string, string> = {
	exercise_block: 'Exercise',
	timer_session: 'Timer',
	checklist_block: 'Checklist'
};

export function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function timerPayload(payload: Record<string, unknown>): TimerPayload {
	return payload as TimerPayload;
}

export function checklistPayload(payload: Record<string, unknown>): ChecklistPayload {
	return payload as ChecklistPayload;
}

export function exercisePayload(payload: Record<string, unknown>): ExercisePayload {
	return payload as ExercisePayload;
}

export function cardBrief(renderer: string, payload: Record<string, unknown>): string {
	if (renderer === 'timer_session') {
		const timer = timerPayload(payload);
		return timer.duration_minutes ? `${timer.duration_minutes} min` : '';
	}
	if (renderer === 'exercise_block') {
		const exercise = exercisePayload(payload);
		return exercise.exercises?.length ? `${exercise.exercises.length} exercises` : '';
	}
	const checklist = checklistPayload(payload);
	return checklist.items?.length ? `${checklist.items.length} items` : '';
}
```

- [ ] **Step 2: Update Today imports and local references**

In `frontend/src/routes/today/+page.svelte`, remove local payload types, `slotAccent`, `rendererIcon`, `rendererLabel`, `isRecord`, `timerPayload`, `checklistPayload`, `exercisePayload`, and local `cardBrief` logic.

Import:

```ts
import {
	RENDERER_ICONS,
	RENDERER_LABELS,
	SLOT_ACCENTS,
	cardBrief as routineCardBrief,
	checklistPayload,
	exercisePayload,
	isRecord,
	timerPayload
} from '$lib/routines/card-payloads';
```

Replace references:

```ts
rendererIcon[card.renderer]
rendererLabel[card.renderer]
slotAccent[slot.slot]
cardBrief(card)
```

with:

```ts
RENDERER_ICONS[card.renderer]
RENDERER_LABELS[card.renderer]
SLOT_ACCENTS[slot.slot as keyof typeof SLOT_ACCENTS]
routineCardBrief(card.renderer, card.payload_json as Record<string, unknown>)
```

- [ ] **Step 3: Update Routine Schedule imports and local references**

In `frontend/src/routes/routines/schedule/+page.svelte`, remove local payload types, slot order/labels/accents/index, renderer icons, and payload casts.

Import:

```ts
import {
	RENDERER_ICONS,
	SLOT_ACCENTS,
	SLOT_INDEX,
	SLOT_LABELS,
	SLOT_ORDER,
	cardBrief,
	checklistPayload,
	exercisePayload,
	timerPayload,
	type SlotName
} from '$lib/routines/card-payloads';
```

Keep `SlotName` compatible with `ScheduleOccurrence['slot']` by using:

```ts
type ScheduleSlotName = ScheduleOccurrence['slot'];
```

Where sorting indexes use:

```ts
SLOT_INDEX[a.slot as SlotName] - SLOT_INDEX[b.slot as SlotName]
```

- [ ] **Step 4: Validate and visually inspect**

Run:

```bash
cd frontend && npm run check
```

Expected: command exits with code `0`.

Use browser MCP screenshots for:

```text
/today
/routines/schedule
```

Expand at least one timer card, checklist card, and exercise card in the Today view. Expand at least one occurrence in Routine Schedule. Expected: icons, slot accents, card brief text, instructions, item lists, and completion status still match baseline.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/routines/card-payloads.ts frontend/src/routes/today/+page.svelte frontend/src/routes/routines/schedule/+page.svelte
git commit -m "refactor(frontend): share routine card payload helpers"
```

---

## Task 9: Final Verification And Cleanup

**Files:**
- Modify: only files already touched by previous tasks if cleanup is needed

- [ ] **Step 1: Search for obvious leftover duplication**

Run:

```bash
rg -n "legend: \\{ labels: \\{ boxWidth: 12|type: 'time'|time: \\{ unit: 'hour'|bg-\\[rgba\\(255,255,255,0\\.02\\)\\] border border-\\[rgba\\(255,255,255,0\\.05\\)\\] rounded-lg p-5|function isoWeekToMonday|type TimerPayload|type ChecklistPayload|type ExercisePayload" frontend/src
```

Expected: remaining matches are either intentionally local because behavior is custom, or are in the new shared modules. Do not chase incidental duplication that would create a generic abstraction with unclear ownership.

- [ ] **Step 2: Run frontend validation**

Run:

```bash
cd frontend && npm run check
```

Expected: command exits with code `0`.

- [ ] **Step 3: Run existing frontend static test if used in the project workflow**

Run:

```bash
cd frontend && node --test tests/metric-daily-api-usage.test.mjs
```

Expected: command exits with code `0`.

- [ ] **Step 4: Full visual pass**

Use browser MCP screenshots for:

```text
/
/heart-rate
/hrv
/sleep
/stress
/body-battery
/respiration
/skin-temp
/pulse-ox
/today
/routines/schedule
```

For metric pages, verify:

- Loading/error shell still renders correctly when applicable.
- Header and trend range controls are still present.
- Stat cards keep their labels, values, units, and colors.
- Charts are nonblank and preserve previous heights.
- Date selector and selected-day intraday panels still work.

For Heart Rate and HRV, also verify:

- Day strip colors and legend labels match the original page.
- Selecting a day opens the history panel.
- Previous/next buttons navigate correctly.
- Clearing selected date returns to `All Days`.

For Today and Routine Schedule, also verify:

- Slot accents and renderer icons match baseline.
- Timer, checklist, and exercise payload sections still render.
- Today status updates still work.

- [ ] **Step 5: Documentation decision**

Do not update `README.md` or `docs/ARCHITECTURE.md` unless the implementation changes routes, setup commands, API endpoints, or top-level project structure. This refactor should not change those.

- [ ] **Step 6: Final commit**

If cleanup produced changes:

```bash
git add frontend/src
git commit -m "refactor(frontend): clean up metric UI duplication"
```

If no cleanup changes were needed, do not create an empty commit.

---

## Rollback Strategy

Each task is independently revertible. If a visual regression appears:

- Revert the most recent task commit.
- Keep earlier completed extraction commits if their visual verification passed.
- Avoid reverting user work outside the touched frontend files.

## Completion Criteria

The refactor is complete only when:

- `cd frontend && npm run check` passes.
- `cd frontend && node --test tests/metric-daily-api-usage.test.mjs` passes.
- Browser MCP visual verification covers every modified route/component listed in Task 9.
- No backend API types were hand-edited.
- No frontend statistical computation was introduced.
