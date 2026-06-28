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

test('hrv page stages baseline snapshots before committing state', () => {
	const page = readFileSync(join('src/routes', 'hrv', '+page.svelte'), 'utf8');

	assert.match(page, /async function loadHrvSnapshot/);
	assert.match(page, /function applyHrvSnapshot/);
	assert.match(
		page,
		/const requestedBaseline = baselineWindow;[\s\S]*const snapshot = await loadHrvSnapshot\(requestedBaseline\);[\s\S]*requestedBaseline !== baselineWindow[\s\S]*applyHrvSnapshot\(snapshot, \{ clearDetailError: selectedDate === '' \}\);/,
	);
	assert.match(page, /const snapshot = await loadHrvSnapshot\(w, selectedForBaseline\);/);
	assert.match(
		page,
		/async function onBaselineChange[\s\S]*\+\+fetchSeq;[\s\S]*const requestId = \+\+baselineRequestId;/,
	);
	assert.match(
		page,
		/applyHistorical: selectedForBaseline !== '' && (selectedForBaseline === selectedDate|selectedDate === selectedForBaseline)/,
	);
	assert.doesNotMatch(page, /agg = nextAgg;[\s\S]{0,300}api\.getHrvInsights/);
});

test('hrv headline does not render the retired recovery status pill', () => {
	const page = readFileSync(join('src/routes', 'hrv', '+page.svelte'), 'utf8');

	assert.doesNotMatch(page, /class="recovery-pill"/);
	assert.doesNotMatch(page, /<span class="stat-label">Recovery<\/span>/);
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
