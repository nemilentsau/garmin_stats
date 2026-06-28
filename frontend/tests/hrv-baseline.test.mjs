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
		/const snapshot = await loadHrvSnapshot\(baselineWindow\);[\s\S]*applyHrvSnapshot\(snapshot, \{ clearDetailError: selectedDate === '' \}\);/,
	);
	assert.match(page, /const snapshot = await loadHrvSnapshot\(w, selectedForBaseline\);/);
	assert.match(
		page,
		/applyHistorical: selectedForBaseline !== '' && (selectedForBaseline === selectedDate|selectedDate === selectedForBaseline)/,
	);
	assert.doesNotMatch(page, /agg = nextAgg;[\s\S]{0,300}api\.getHrvInsights/);
});
