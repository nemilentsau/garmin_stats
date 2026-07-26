import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

test('runs commits filter responses only while their request remains current', () => {
	const page = readFileSync('src/routes/runs/+page.svelte', 'utf8');

	assert.match(page, /const loadRuns = createLatestLoader\(/);
});

test('schedule tracks requested and loaded dates and handles navigation errors', () => {
	const page = readFileSync('src/routes/training/schedule/+page.svelte', 'utf8');

	assert.match(page, /let loadedStartDate = \$state<string \| null>\(null\)/);
	assert.match(page, /const loadSchedule = createLatestLoader\(/);
	assert.match(page, /error = errorMessage\(cause\)/);
});
