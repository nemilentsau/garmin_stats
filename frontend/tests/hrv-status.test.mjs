import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';

test('garminStatusKey hides the chip for an absent / Unknown Garmin status', () => {
	const src = readFileSync(join('src/lib', 'hrv-status.ts'), 'utf8');
	// Absent status (null/empty) → null so the {#if key} chip guard fails.
	assert.match(src, /if \(!status\) return null;/);
	// The backend normalizes a none/null Garmin status to the literal "Unknown"; treat that
	// as absent too, so status-less nights show no chip (spec: "Garmin status absent: hidden").
	assert.match(src, /=== 'Unknown' \? null : key/);
});

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
