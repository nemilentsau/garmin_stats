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

test('hrv window and detail loads use orthogonal tokens so neither cancels the other', () => {
	const page = readFileSync(join('src/routes', 'hrv', '+page.svelte'), 'utf8');

	// Window/chart loads and the night-detail panel are ORTHOGONAL concerns carrying DISJOINT
	// request tokens, so a night click can't cancel an in-flight baseline switch (the reverting-
	// window bug) and a switch can't cancel a night fetch. (The stale-completion decision itself —
	// whether a finished load should apply its night — is unit-tested behaviourally in
	// lib-helpers.test.mjs via historicalApplyOptions; here we assert the page wires the tokens.)
	assert.match(page, /async function loadHrvSnapshot/);
	assert.match(page, /function applyHrvSnapshot/);
	assert.match(page, /async function onBaselineChange[\s\S]*?\+\+windowReq/);
	assert.match(page, /async function fetchData[\s\S]*?\+\+windowReq/);
	assert.match(page, /async function onDateChange[\s\S]*?\+\+detailReq/);
	// A baseline switch guards on windowReq; a night fetch guards on detailReq — different tokens.
	assert.match(page, /async function onBaselineChange[\s\S]*?if \(myReq !== windowReq\) return;/);
	assert.match(page, /async function onDateChange[\s\S]*?if \(myReq !== detailReq\) return;/);

	// The committed window moves only inside applyHrvSnapshot (atomically with the chart data),
	// never eagerly in onBaselineChange, so a superseded switch leaves every surface coherent.
	assert.match(page, /function applyHrvSnapshot[\s\S]*?baselineWindow = snapshot\.baseline;/);
	assert.doesNotMatch(page, /async function onBaselineChange[\s\S]*?baselineWindow = w;/);
	// The picker highlight is optimistic and does not move the committed window; baselineLoading is
	// DERIVED from it (one source of truth) so the spinner can't stick.
	assert.match(page, /value=\{pendingBaseline \?\? baselineWindow\}/);
	assert.match(page, /\$derived\(pendingBaseline !== null\)/);

	// The stale-completion predicate and the error-message idiom are SHARED helpers (tested in
	// lib-helpers.test.mjs), not inlined / copy-pasted per handler.
	assert.match(page, /\$lib\/hrv-async/);
	assert.match(page, /historicalApplyOptions\(/);
	assert.match(page, /\$lib\/errors/);
	assert.match(page, /errorMessage\(/);

	// Baseline switch reuses the window-independent daily aggregate + overview instead of
	// re-fetching them; only the window-dependent analysis + insights are fetched.
	assert.match(page, /reuse = agg && dashOverview \? \{ agg, dashOverview \} : undefined/);

	// The selected-night sub-fetch is isolated inside loadHrvSnapshot: a failure is surfaced via
	// detailError instead of rejecting the whole snapshot, so a failed night fetch can't blank the
	// chart/headline.
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
	// Strip colors come from the trend_state of the nightly trend (averages), not Garmin per-night
	// status. Color + label share one source map (TREND_STATES) so they can't drift apart.
	assert.match(page, /TREND_STATES/);
	assert.match(page, /nightly_trend[\s\S]*?trend_state/);
	// The day cell color is driven by the strip's date→color map built from trend_state.
	assert.match(page, /strip\.map\.get\(day\) \?\? UNKNOWN_STATUS_COLOR/);
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
	// The cell stride lives in one place (--day-cell-w / --day-strip-gap on .day-nav); the cells
	// and the month axis both derive from it via var(), so they can't fall out of alignment.
	// (The exact px value isn't pinned — only that the single source var exists and is reused.)
	assert.match(page, /\.day-nav\s*\{[\s\S]*--day-cell-w:/);
	assert.match(page, /\.day-cell\s*\{[\s\S]*min-width:\s*var\(--day-cell-w\);/);
	assert.match(page, /class="month-tick" style="--days: \{seg\.count\};"/);
	assert.match(
		page,
		/\.month-tick\s*\{[\s\S]*flex:\s*0 0 calc\(var\(--days\) \* \(var\(--day-cell-w\) \+ var\(--day-strip-gap\)\)\);/,
	);
});
