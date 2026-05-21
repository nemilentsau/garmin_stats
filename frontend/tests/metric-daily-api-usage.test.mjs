import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';

const metricPages = [
	['heart-rate', 'getHeartRateDaily'],
	['hrv', 'getHrvDaily'],
	['sleep', 'getSleepDaily'],
	['stress', 'getStressDaily'],
	['body-battery', 'getBodyBatteryDaily'],
	['respiration', 'getRespirationDaily'],
	['skin-temp', 'getSkinTempDaily'],
	['pulse-ox', 'getPulseOxDaily']
];

test('metric detail pages use metric-scoped daily APIs', () => {
	for (const [route, expectedMethod] of metricPages) {
		const source = readFileSync(join('src/routes', route, '+page.svelte'), 'utf8');

		assert.match(source, new RegExp(`api\\.${expectedMethod}\\(`), route);
		assert.doesNotMatch(source, /api\.getDailyAggregates\(/, route);
		assert.doesNotMatch(source, /\bDailyAggregates\b/, route);
	}
});

test('metric stat cards do not use runtime-built Tailwind color classes', () => {
	for (const [route] of metricPages) {
		const source = readFileSync(join('src/routes', route, '+page.svelte'), 'utf8');

		assert.doesNotMatch(source, /colorClass="text-\[\{/, route);
		assert.doesNotMatch(source, /colorClass=\{`text-\[\$\{/, route);
	}
});

test('api client uses a shared unwrap helper instead of per-method boilerplate', () => {
	const source = readFileSync(join('src/lib', 'api.ts'), 'utf8');

	assert.match(source, /async function unwrapResponse</);
	assert.doesNotMatch(source, /const \{ data, error \} = await client\.(GET|POST|PUT)/);
});

test('routine surfaces share card payload helpers', () => {
	const todaySource = readFileSync(join('src/routes', 'today', '+page.svelte'), 'utf8');
	const scheduleSource = readFileSync(
		join('src/routes', 'routines', 'schedule', '+page.svelte'),
		'utf8'
	);

	for (const source of [todaySource, scheduleSource]) {
		assert.match(source, /\$lib\/routines\/card-payloads/);
		assert.doesNotMatch(source, /type TimerPayload/);
		assert.doesNotMatch(source, /type ChecklistPayload/);
		assert.doesNotMatch(source, /type ExercisePayload/);
		assert.doesNotMatch(source, /function timerPayload/);
		assert.doesNotMatch(source, /function checklistPayload/);
		assert.doesNotMatch(source, /function exercisePayload/);
	}

	assert.doesNotMatch(todaySource, /const slotAccent/);
	assert.doesNotMatch(todaySource, /const rendererIcon/);
	assert.doesNotMatch(todaySource, /const rendererLabel/);
	assert.doesNotMatch(todaySource, /function cardBrief/);
	assert.doesNotMatch(scheduleSource, /const SLOT_ORDER/);
	assert.doesNotMatch(scheduleSource, /const SLOT_LABELS/);
	assert.doesNotMatch(scheduleSource, /const SLOT_ACCENTS/);
	assert.doesNotMatch(scheduleSource, /const SLOT_INDEX/);
	assert.doesNotMatch(scheduleSource, /const RENDERER_ICONS/);
	assert.doesNotMatch(scheduleSource, /function cardBrief/);
});
