/**
 * Unit tests for rating-helpers.ts — the shared rating-prompt state helpers used by
 * StrengthSessionCard and MeditationTimerCard.
 *
 * The backend contract types ratings as dict[str, int]; cleanRatings enforces integers
 * (round + finite check) at the serialization boundary so a typed decimal can never 422
 * the whole log update.
 */
import assert from 'node:assert/strict';
import test from 'node:test';
import { createServer } from 'vite';

let server;
let helpers;

test.before(async () => {
	server = await createServer({
		configFile: 'vite.config.ts',
		server: { middlewareMode: true },
		appType: 'custom',
		logLevel: 'error'
	});
	helpers = await server.ssrLoadModule('/src/lib/routines/cards/rating-helpers.ts');
});

test.after(async () => {
	await server?.close();
});

// ── buildInitialRatings ──────────────────────────────────────────────────────

test('buildInitialRatings with no existing ratings: all prompt keys null', () => {
	const { buildInitialRatings } = helpers;
	const prompts = [
		{ key: 'rpe', label: 'RPE', scale_min: 1, scale_max: 10 },
		{ key: 'mood', label: 'Mood', scale_min: 1, scale_max: 5 }
	];
	assert.deepEqual(buildInitialRatings(prompts, null), { rpe: null, mood: null });
});

test('buildInitialRatings restores saved values and nulls missing keys', () => {
	const { buildInitialRatings } = helpers;
	const prompts = [
		{ key: 'rpe', label: 'RPE', scale_min: 1, scale_max: 10 },
		{ key: 'mood', label: 'Mood', scale_min: 1, scale_max: 5 }
	];
	const result = buildInitialRatings(prompts, { rpe: 8 });
	assert.equal(result.rpe, 8);
	assert.equal(result.mood, null);
});

// ── cleanRatings ─────────────────────────────────────────────────────────────

test('cleanRatings drops null and non-finite values', () => {
	const { cleanRatings } = helpers;
	assert.deepEqual(cleanRatings({ calm: 4, focus: null, drift: NaN }), { calm: 4 });
});

test('cleanRatings rounds fractional ratings to integers', () => {
	const { cleanRatings } = helpers;
	assert.deepEqual(cleanRatings({ calm: 3.5, focus: 4 }), { calm: 4, focus: 4 });
});
