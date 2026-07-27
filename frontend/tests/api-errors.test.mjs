import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

test('API failures preserve HTTP status and training import distinguishes absence', () => {
	const api = readFileSync('src/lib/api.ts', 'utf8');
	const page = readFileSync('src/routes/training/import/+page.svelte', 'utf8');

	assert.match(api, /export class ApiError extends Error/);
	assert.match(api, /readonly status: number/);
	assert.match(page, /error instanceof ApiError && error\.status === 404/);
	assert.doesNotMatch(page, /const MAX_PACKAGE_BYTES/);
});
