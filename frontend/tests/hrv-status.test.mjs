import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';

// garminStatusKey's input→output behaviour (absent / Unknown / title-casing) is covered
// behaviourally in lib-helpers.test.mjs; this file only asserts how the page wires the chip.

test('hrv chip reads the raw Garmin status once via garminStatusKey (no double-keying)', () => {
	const page = readFileSync(join('src/routes', 'hrv', '+page.svelte'), 'utf8');
	// Helper imported; the key is computed inside the chip snippet only.
	assert.match(page, /\$lib\/hrv-status/);
	assert.match(page, /\{@const key = garminStatusKey\(status\)\}/);
	// Call sites pass the raw per-day status, not a pre-keyed value — so the key is computed
	// exactly once (the old statusKey(statusKey(...)) double application is gone).
	assert.match(page, /garminChip\(latestDayStats\?\.status\)/);
	assert.match(page, /garminChip\(historicalDayStats\?\.status\)/);
	assert.doesNotMatch(page, /statusKey\(statusKey\(/);
	assert.doesNotMatch(page, /function statusKey/);
});
