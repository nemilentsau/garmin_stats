import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import test from 'node:test';

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

test('v2 routine and artifact frontend surfaces stay retired', () => {
	const api = readFileSync('src/lib/api.ts', 'utf8');
	const layout = readFileSync('src/routes/+layout.svelte', 'utf8');
	const today = readFileSync('src/routes/today/+page.svelte', 'utf8');

	assert.equal(existsSync('src/lib/routines'), false);
	assert.equal(existsSync('src/routes/routines'), false);
	assert.equal(existsSync('src/routes/training/schedule/+page.svelte'), true);
	assert.equal(layout.includes("href: '/training/schedule'"), true);
	assert.equal(layout.includes("href: '/routines"), false);
	assert.equal(today.includes('routine-select'), false);

	for (const retiredMethod of [
		'getToday',
		'updateTodayCard',
		'getCardLogsRange',
		'getRoutines',
		'getRoutineScheduleWindow',
		'previewAssistantArtifactBundle',
		'importAssistantArtifactBundle'
	]) {
		assert.equal(api.includes(`${retiredMethod}:`), false, retiredMethod);
	}
});
