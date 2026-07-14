import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { createServer } from 'vite';

let server;
let state;

test.before(async () => {
	server = await createServer({
		configFile: 'vite.config.ts',
		server: { middlewareMode: true },
		appType: 'custom',
		logLevel: 'error'
	});
	state = await server.ssrLoadModule('/src/lib/today-state.ts').catch(() => null);
	assert.notEqual(state, null, 'Today state helpers must be extracted from the page');
});

test.after(async () => {
	await server?.close();
});

test('local status overrides backend status and completion toggles symmetrically', () => {
	assert.equal(
		state.effectiveStatus({ occurrence_key: 'card-1', status: 'pending' }, { 'card-1': 'partial' }),
		'partial'
	);
	assert.equal(state.toggledCompletionStatus('completed'), 'pending');
	assert.equal(state.toggledCompletionStatus('skipped'), 'completed');
});

test('only the authored skip variant changes status', () => {
	assert.equal(state.statusForVariant('skip', 'partial'), 'skipped');
	assert.equal(state.statusForVariant('reduced volume', 'partial'), 'partial');
});

test('checklist status distinguishes untouched, partial, and complete answers', () => {
	const kinds = { core: 'checkbox', quad: 'tissue_check' };
	assert.equal(state.deriveChecklistStatus([], kinds), 'pending');
	assert.equal(
		state.deriveChecklistStatus(
			[{ item_id: 'core', checked: true, scale: null }, { item_id: 'quad', checked: false, scale: null }],
			kinds
		),
		'partial'
	);
	assert.equal(
		state.deriveChecklistStatus(
			[{ item_id: 'core', checked: true, scale: null }, { item_id: 'quad', checked: false, scale: 0 }],
			kinds
		),
		'completed'
	);
});

test('Today page uses one feed action path and one shared row component', () => {
	const source = readFileSync('src/routes/today/+page.svelte', 'utf8');

	assert.equal(source.includes('toggleTrainingComplete'), false);
	assert.equal(source.includes('quickTrainingSkip'), false);
	assert.equal(source.includes('scheduleTrainingPersistDetail'), false);
	assert.equal(source.includes('selectTrainingVariant'), false);
	assert.equal(source.includes('TodayActivityRow'), true);
});

test('routine and training tissue check-ins share one row component', () => {
	const routineSource = readFileSync('src/lib/routines/cards/ChecklistCard.svelte', 'utf8');
	const trainingSource = readFileSync('src/lib/training/TrainingCheckinGrid.svelte', 'utf8');

	for (const source of [routineSource, trainingSource]) {
		assert.equal(source.includes('TissueCheckRow'), true);
		assert.equal(source.includes('class="scale-chips"'), false);
	}
});
