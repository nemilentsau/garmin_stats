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
