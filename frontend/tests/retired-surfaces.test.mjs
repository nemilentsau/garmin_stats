import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import test from 'node:test';

test('legacy routine runtime excludes retired v2 training renderers', () => {
	const dispatcher = readFileSync('src/lib/routines/cards/CardBody.svelte', 'utf8');

	assert.equal(dispatcher.includes('RunningWorkoutCard'), false);
	assert.equal(dispatcher.includes('StrengthSessionCard'), false);
	assert.equal(existsSync('src/lib/routines/cards/RunningWorkoutCard.svelte'), false);
	assert.equal(existsSync('src/lib/routines/cards/StrengthSessionCard.svelte'), false);
});

test('unreferenced frontend scaffolding and helpers stay removed', () => {
	const format = readFileSync('src/lib/format.ts', 'utf8');
	const utils = readFileSync('src/lib/utils.ts', 'utf8');
	const packageJson = readFileSync('package.json', 'utf8');

	assert.equal(existsSync('src/lib/components/ScatterChart.svelte'), false);
	assert.equal(existsSync('src/lib/index.ts'), false);
	assert.equal(format.includes('fmtTimeWindow'), false);
	assert.equal(utils.includes('makeId'), false);
	assert.equal(utils.includes('isRecord'), false);
	assert.equal(packageJson.includes('@types/dompurify'), false);
});

test('API client exposes only methods used by the shipped frontend', () => {
	const source = readFileSync('src/lib/api.ts', 'utf8');
	const retiredMethods = [
		'getHrvRaw',
		'getSkinTempRaw',
		'triggerIngest',
		'getProfile',
		'updateProfile',
		'getRoutineAssignments',
		'getCards',
		'getCheckins',
		'createCheckin',
		'getNotes',
		'createNote',
		'getExperimentAnalysis',
		'createExperiment',
		'updateExperiment',
		'refreshExperimentAnalyses',
		'getTargetMetrics',
		'getAssistantArtifacts',
		'createAssistantArtifact',
		'activateAssistantArtifact',
		'getCoachReview',
		'getCoachJob',
		'getCoachJournal'
	];

	for (const method of retiredMethods) {
		assert.equal(source.includes(`${method}:`), false, method);
	}
});
