import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';

test('hrv baseline windows have one frontend source of truth', () => {
	const page = readFileSync(join('src/routes', 'hrv', '+page.svelte'), 'utf8');
	const picker = readFileSync(join('src/lib/components', 'BaselineWindowPicker.svelte'), 'utf8');

	assert.match(page, /\$lib\/hrv-baseline/);
	assert.match(page, /coerceHrvBaselineWindow/);
	assert.doesNotMatch(page, /const ALLOWED_WINDOWS/);
	assert.match(picker, /\$lib\/hrv-baseline/);
	assert.match(picker, /HRV_BASELINE_WINDOWS/);
	assert.doesNotMatch(picker, /const WINDOWS/);
});

test('hrv async paths stage snapshots and guard against stale completions', () => {
	const page = readFileSync(join('src/routes', 'hrv', '+page.svelte'), 'utf8');

	// Staging pattern: load into an immutable snapshot, then commit it atomically. Never
	// commit by assigning agg straight from a freshly-fetched value next to an insights
	// call — that would write partial state before the snapshot is staged.
	assert.match(page, /async function loadHrvSnapshot/);
	assert.match(page, /function applyHrvSnapshot/);
	assert.doesNotMatch(page, /agg = nextAgg;[\s\S]{0,300}api\.getHrvInsights/);

	// One monotonic request token shared by every async path; the three independent
	// counters that used to race (date / baseline / fetch) are gone.
	assert.match(page, /let reqId = 0;/);
	assert.doesNotMatch(page, /baselineRequestId|dateRequestId|fetchSeq/);

	// Each async path captures the token on entry and guards before committing, so a stale
	// completion (date-vs-date, baseline-vs-date, SSE-vs-anything) cannot overwrite fresher
	// state.
	assert.match(
		page,
		/async function fetchData[\s\S]*?const myReq = \+\+reqId;[\s\S]*?if \(myReq !== reqId\) return;/,
	);
	assert.match(
		page,
		/async function onBaselineChange[\s\S]*?const myReq = \+\+reqId;[\s\S]*?if \(myReq !== reqId\) return;/,
	);
	assert.match(
		page,
		/async function onDateChange[\s\S]*?const myReq = \+\+reqId;[\s\S]*?if \(myReq !== reqId\) return;/,
	);

	// Baseline switch loads with the selected night and commits historical only while that
	// night is still selected, so the chart and the panel agree for a night + window.
	assert.match(page, /loadHrvSnapshot\(w, selectedForBaseline, reuse\)/);
	assert.match(
		page,
		/applyHistorical: selectedForBaseline !== '' && selectedForBaseline === selectedDate/,
	);

	// Baseline switch reuses the window-independent daily aggregate + overview instead of
	// re-fetching them; only the window-dependent analysis + insights are fetched.
	assert.match(
		page,
		/reuse = agg && dashOverview \? \{ agg, dashOverview \} : undefined/,
	);
	assert.match(page, /reuse\s*\?\s*\[reuse\.agg, reuse\.dashOverview\]/);

	// SSE refresh refetches the open night so the panel z-score can't go stale while the
	// chart's bands move underneath it.
	assert.match(
		page,
		/async function fetchData[\s\S]*?const historicalDate = selectedDate;[\s\S]*?loadHrvSnapshot\(requestedBaseline, historicalDate\)/,
	);

	// The rendered window commits atomically with the chart data inside applyHrvSnapshot —
	// never eagerly in onBaselineChange — so the picker, legend, URL, chart band and panel z
	// can't disagree on the window when a switch is superseded (C4).
	assert.match(page, /function applyHrvSnapshot[\s\S]*?baselineWindow = snapshot\.baseline;/);
	assert.doesNotMatch(
		page,
		/async function onBaselineChange[\s\S]*?baselineWindow = w;/,
	);
	// The picker highlight is optimistic (pendingBaseline) and does not move the committed window.
	assert.match(page, /pendingBaseline = w;/);
	assert.match(page, /value=\{pendingBaseline \?\? baselineWindow\}/);

	// The spinner + optimistic highlight are owned by the latest baseline switch and cleared in
	// finally even when superseded by a night click / SSE refresh, so baselineLoading can never
	// stick (C3).
	assert.match(
		page,
		/async function onBaselineChange[\s\S]*?baselineReq = myReq;[\s\S]*?finally \{[\s\S]*?if \(baselineReq === myReq\) \{[\s\S]*?baselineLoading = false;/,
	);

	// The selected-night sub-fetch is isolated inside loadHrvSnapshot: a failure is captured as
	// historicalError and surfaced via detailError instead of rejecting the whole snapshot, so a
	// failed night fetch on an SSE refresh can't blank the chart/headline (C5).
	assert.match(
		page,
		/getHrvInsights\(historicalDate, window\)[\s\S]*?\.catch\(/,
	);
	assert.match(page, /detailError = snapshot\.historicalError;/);
});

test('hrv headline does not render the retired recovery status pill', () => {
	const page = readFileSync(join('src/routes', 'hrv', '+page.svelte'), 'utf8');

	assert.doesNotMatch(page, /class="recovery-pill"/);
	assert.doesNotMatch(page, /<span class="stat-label">Recovery<\/span>/);
});

test('hrv surfaces Garmin status as its own labelled chip, separate from the verdict', () => {
	const page = readFileSync(join('src/routes', 'hrv', '+page.svelte'), 'utf8');
	assert.match(page, /class="garmin-chip"/);
	assert.match(page, /Garmin:/);
	// The chip reads the raw Garmin per-day status, not the recovery verdict.
	assert.match(page, /garminChip\((historicalDayStats|latestDayStats)\?\.status\)/);
});

test('hrv history strip is colored by the averaged trend, not per-night status', () => {
	const page = readFileSync(join('src/routes', 'hrv', '+page.svelte'), 'utf8');
	// Strip colors come from the trend_state of the nightly trend (averages), not Garmin per-night status.
	assert.match(page, /TREND_STATE_COLORS/);
	assert.match(page, /nightly_trend[\s\S]*?trend_state/);
	// The day cell color is driven by dayStatusMap built from trend_state.
	assert.match(page, /dayStatusMap\.get\(day\) \?\? UNKNOWN_STATUS_COLOR/);
	// Gray (warmup / no trend) is a labelled legend entry, not a mystery.
	assert.match(page, /Building baseline/);
	// The strip legend stays visible while the timeline scrolls horizontally.
	assert.match(page, /\.day-strip-legend\s*\{[\s\S]*position:\s*sticky;[\s\S]*left:\s*0;/);
});

test('hrv history strip keeps nights selectable instead of compressing all days', () => {
	const page = readFileSync(join('src/routes', 'hrv', '+page.svelte'), 'utf8');

	assert.match(page, /bind:this=\{dayStripContainer\}/);
	assert.match(page, /function scrollTimelineToLatestOnce/);
	assert.match(page, /dayStripContainer\.scrollLeft = dayStripContainer\.scrollWidth;/);
	assert.match(page, /\.day-strip-container\s*\{[\s\S]*overflow-x:\s*auto;/);
	assert.match(page, /\.day-cell\s*\{[\s\S]*min-width:\s*8px;/);
	assert.match(page, /class="month-tick" style="--days: \{seg\.count\};"/);
	assert.match(page, /\.month-tick\s*\{[\s\S]*flex:\s*0 0 calc\(var\(--days\) \* 10px\);/);
});
