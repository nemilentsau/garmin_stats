import assert from 'node:assert/strict';
import test from 'node:test';
import { createServer } from 'vite';

// Behavioral unit tests for the HRV tab's pure helpers. These exercise real input → output
// (loaded through Vite so the TS modules run as-is) instead of regex-matching +page.svelte source
// text — so a behaviour-preserving refactor stays green while an actual logic regression fails.

let server;
let format;
let errors;
let hrvAsync;
let hrvStatus;
let realtimePage;

test.before(async () => {
	server = await createServer({
		configFile: 'vite.config.ts',
		optimizeDeps: { noDiscovery: true },
		server: { middlewareMode: true, hmr: false },
		appType: 'custom',
		logLevel: 'error'
	});
	format = await server.ssrLoadModule('/src/lib/format.ts');
	errors = await server.ssrLoadModule('/src/lib/errors.ts');
	hrvAsync = await server.ssrLoadModule('/src/lib/hrv-async.ts');
	hrvStatus = await server.ssrLoadModule('/src/lib/hrv-status.ts');
	realtimePage = await server.ssrLoadModule('/src/lib/realtime-page.ts');
});

test.after(async () => {
	await server?.close();
});

test('fmtSigned prefixes + only when positive after rounding, and keeps the requested precision', () => {
	const { fmtSigned } = format;
	assert.equal(fmtSigned(2.5), '+2.5');
	assert.equal(fmtSigned(-2.5), '-2.5');
	// The selected-night z is authored at 2 decimals; rendering at 2dp must not collapse 2.03→2.0,
	// or the shown number would contradict the |z| > 2.0 "extreme night" flag.
	assert.equal(fmtSigned(2.03, 2), '+2.03');
	assert.notEqual(fmtSigned(2.03, 2), '+2.0');
});

test('fmtSigned never renders a signed negative zero', () => {
	const { fmtSigned } = format;
	// A tiny negative that rounds to zero at the requested precision is zero — "0.0", not "-0.0".
	assert.equal(fmtSigned(-0.04, 1), '0.0');
	assert.equal(fmtSigned(-0.004, 2), '0.00');
	assert.equal(fmtSigned(0, 1), '0.0');
});

test('fmtSigned returns a dash for null/undefined', () => {
	const { fmtSigned } = format;
	assert.equal(fmtSigned(null), '-');
	assert.equal(fmtSigned(undefined), '-');
});

test('errorMessage reads .message from an Error and stringifies anything else', () => {
	const { errorMessage } = errors;
	assert.equal(errorMessage(new Error('boom')), 'boom');
	assert.equal(errorMessage('plain'), 'plain');
	assert.equal(errorMessage(404), '404');
});

test('historicalApplyOptions applies a night only while it is still the selected one', () => {
	const { historicalApplyOptions } = hrvAsync;
	// Captured night still selected → apply it (and clear any stale error).
	assert.deepEqual(historicalApplyOptions('2026-01-10', '2026-01-10'), {
		applyHistorical: true,
		clearDetailError: true
	});
	// User moved to another night before the load finished → must NOT clobber the fresher pick.
	assert.deepEqual(historicalApplyOptions('2026-01-10', '2026-01-11'), {
		applyHistorical: false,
		clearDetailError: false
	});
	// Nothing was open when the load started → nothing to apply, safe to clear a stale error.
	assert.deepEqual(historicalApplyOptions('', '2026-01-11'), {
		applyHistorical: false,
		clearDetailError: true
	});
	// Night was open at start but closed before finish → don't apply, don't clear (panel is gone).
	assert.deepEqual(historicalApplyOptions('2026-01-10', ''), {
		applyHistorical: false,
		clearDetailError: false
	});
});

test('garminStatusKey title-cases a present status and hides absent / Unknown', () => {
	const { garminStatusKey } = hrvStatus;
	assert.equal(garminStatusKey('balanced'), 'Balanced');
	assert.equal(garminStatusKey('UNBALANCED'), 'Unbalanced');
	assert.equal(garminStatusKey(null), null);
	assert.equal(garminStatusKey(''), null);
	assert.equal(garminStatusKey(undefined), null);
	// The backend normalizes an absent Garmin status to the literal "Unknown" → no chip.
	assert.equal(garminStatusKey('unknown'), null);
});

test('latest request gate invalidates stale selected-date refreshes', () => {
	const gate = realtimePage.createLatestRequestGate();
	const first = gate.issue();
	assert.equal(gate.isCurrent(first), true);

	gate.invalidate();
	assert.equal(gate.isCurrent(first), false);

	const second = gate.issue();
	assert.equal(gate.isCurrent(second), true);
	assert.equal(gate.isCurrent(first), false);
});
