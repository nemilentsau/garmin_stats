import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { createServer } from 'vite';

let server;
let state;

test.before(async () => {
	server = await createServer({
		configFile: 'vite.config.ts',
		optimizeDeps: { noDiscovery: true },
		server: { middlewareMode: true, hmr: false },
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

test('rapid optimistic writes serialize and roll back to the last confirmed status', async () => {
	const events = [];
	let current = 'completed';
	const queue = state.createStatusPersistQueue();

	queue.enqueue({
		key: '2026-07-15:card',
		attempted: 'completed',
		initialConfirmed: 'pending',
		persist: async () => {
			events.push('completed');
			return false;
		},
		isCurrent: () => current === 'completed',
		rollback: (confirmed) => { current = confirmed; }
	});
	current = 'skipped';
	await queue.enqueue({
		key: '2026-07-15:card',
		attempted: 'skipped',
		initialConfirmed: 'completed',
		persist: async () => {
			events.push('skipped');
			return false;
		},
		isCurrent: () => current === 'skipped',
		rollback: (confirmed) => { current = confirmed; }
	});

	assert.deepEqual(events, ['completed', 'skipped']);
	assert.equal(current, 'pending');
});

test('Today page uses one feed action path and one shared row component', () => {
	const source = readFileSync('src/routes/today/+page.svelte', 'utf8');

	assert.equal(source.includes('toggleTrainingComplete'), false);
	assert.equal(source.includes('quickTrainingSkip'), false);
	assert.equal(source.includes('scheduleTrainingPersistDetail'), false);
	assert.equal(source.includes('selectTrainingVariant'), false);
	assert.equal(source.includes('TodayActivityRow'), true);
});

test('training tissue check-ins use the shared row component', () => {
	const trainingSource = readFileSync('src/lib/training/TrainingCheckinGrid.svelte', 'utf8');

	assert.equal(trainingSource.includes('TissueCheckRow'), true);
	assert.equal(trainingSource.includes('class="scale-chips"'), false);
});
