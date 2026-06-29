/**
 * Unit tests for strength-helpers.ts — the pure functions that build initial log state
 * and serialize it back to the StrengthActual wire shape (with NaN coercion).
 *
 * These are data-integrity tests for the fix that replaced the reactive $effect re-seed
 * with a one-time synchronous init. Covers: prescribed-only init, prefill from actual,
 * extra exercises in actual, and NaN→null coercion in serializeExercises/coerceSet.
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
	helpers = await server.ssrLoadModule(
		'/src/lib/routines/cards/strength-helpers.ts'
	);
});

test.after(async () => {
	await server?.close();
});

// ── buildInitialExercises ────────────────────────────────────────────────────

test('buildInitialExercises with no actual: pre-seeds one empty set per prescribed exercise', () => {
	const { buildInitialExercises } = helpers;
	const prescribed = [
		{ id: 'sq', label: 'Squat', set_scheme: '3x5' },
		{ id: 'bp', label: 'Bench', set_scheme: '3x5' }
	];
	const result = buildInitialExercises(prescribed, null);
	assert.equal(result.length, 2);
	assert.equal(result[0].exercise_id, 'sq');
	assert.equal(result[0].is_extra, false);
	assert.equal(result[0].sets.length, 1);
	assert.deepEqual(result[0].sets[0], { set_index: 0, weight: null, reps: null, rir: null });
	assert.equal(result[1].exercise_id, 'bp');
});

test('buildInitialExercises with existing actual: restores all exercises and set values', () => {
	const { buildInitialExercises } = helpers;
	const prescribed = [{ id: 'sq', label: 'Squat' }];
	const actual = {
		card_type: 'strength_session',
		exercises: [
			{
				exercise_id: 'sq',
				label: 'Squat',
				is_extra: false,
				sets: [
					{ set_index: 0, weight: 100, reps: 5, rir: 2 },
					{ set_index: 1, weight: 105, reps: 4, rir: 1 }
				]
			}
		],
		ratings: {}
	};
	const result = buildInitialExercises(prescribed, actual);
	assert.equal(result.length, 1);
	assert.equal(result[0].sets.length, 2);
	assert.deepEqual(result[0].sets[0], { set_index: 0, weight: 100, reps: 5, rir: 2 });
	assert.deepEqual(result[0].sets[1], { set_index: 1, weight: 105, reps: 4, rir: 1 });
});

test('buildInitialExercises with existing actual: restores extra exercises', () => {
	const { buildInitialExercises } = helpers;
	const prescribed = [{ id: 'sq', label: 'Squat' }];
	const actual = {
		card_type: 'strength_session',
		exercises: [
			{
				exercise_id: 'sq',
				label: null,
				is_extra: false,
				sets: [{ set_index: 0, weight: 80, reps: 8, rir: 3 }]
			},
			{
				exercise_id: null,
				label: 'Calf raises',
				is_extra: true,
				sets: [{ set_index: 0, weight: 60, reps: 15, rir: 0 }]
			}
		],
		ratings: {}
	};
	const result = buildInitialExercises(prescribed, actual);
	assert.equal(result.length, 2);
	assert.equal(result[1].is_extra, true);
	assert.equal(result[1].label, 'Calf raises');
	assert.deepEqual(result[1].sets[0], { set_index: 0, weight: 60, reps: 15, rir: 0 });
});

// ── buildInitialRatings ──────────────────────────────────────────────────────

test('buildInitialRatings with no actual: all keys set to null', () => {
	const { buildInitialRatings } = helpers;
	const prompts = [
		{ key: 'rpe', label: 'RPE', scale_min: 1, scale_max: 10 },
		{ key: 'mood', label: 'Mood', scale_min: 1, scale_max: 5 }
	];
	const result = buildInitialRatings(prompts, null);
	assert.deepEqual(result, { rpe: null, mood: null });
});

test('buildInitialRatings with existing actual: restores saved values, nulls missing keys', () => {
	const { buildInitialRatings } = helpers;
	const prompts = [
		{ key: 'rpe', label: 'RPE', scale_min: 1, scale_max: 10 },
		{ key: 'mood', label: 'Mood', scale_min: 1, scale_max: 5 }
	];
	const actual = {
		card_type: 'strength_session',
		exercises: [],
		ratings: { rpe: 8 }
	};
	const result = buildInitialRatings(prompts, actual);
	assert.equal(result.rpe, 8);
	assert.equal(result.mood, null);
});

// ── coerceSet ────────────────────────────────────────────────────────────────

test('coerceSet converts NaN to null, leaves finite numbers unchanged', () => {
	const { coerceSet } = helpers;
	assert.deepEqual(
		coerceSet({ set_index: 0, weight: NaN, reps: NaN, rir: NaN }),
		{ set_index: 0, weight: null, reps: null, rir: null }
	);
	assert.deepEqual(
		coerceSet({ set_index: 1, weight: 100, reps: 5, rir: 2 }),
		{ set_index: 1, weight: 100, reps: 5, rir: 2 }
	);
	// Mixed: only NaN fields become null
	assert.deepEqual(
		coerceSet({ set_index: 2, weight: 75.5, reps: NaN, rir: null }),
		{ set_index: 2, weight: 75.5, reps: null, rir: null }
	);
});

test('coerceSet converts null to null (already conformant)', () => {
	const { coerceSet } = helpers;
	assert.deepEqual(
		coerceSet({ set_index: 0, weight: null, reps: null, rir: null }),
		{ set_index: 0, weight: null, reps: null, rir: null }
	);
});

// ── serializeExercises ───────────────────────────────────────────────────────

test('serializeExercises applies NaN coercion to all sets across all exercises', () => {
	const { serializeExercises } = helpers;
	const exercises = [
		{
			exercise_id: 'sq',
			label: null,
			is_extra: false,
			sets: [
				{ set_index: 0, weight: 100, reps: 5, rir: 2 },
				{ set_index: 1, weight: NaN, reps: NaN, rir: NaN }
			]
		},
		{
			exercise_id: null,
			label: 'Cable curl',
			is_extra: true,
			sets: [{ set_index: 0, weight: NaN, reps: 12, rir: null }]
		}
	];
	const result = serializeExercises(exercises);
	assert.deepEqual(result[0].sets[0], { set_index: 0, weight: 100, reps: 5, rir: 2 });
	assert.deepEqual(result[0].sets[1], { set_index: 1, weight: null, reps: null, rir: null });
	assert.deepEqual(result[1].sets[0], { set_index: 0, weight: null, reps: 12, rir: null });
	assert.equal(result[1].is_extra, true);
	assert.equal(result[1].label, 'Cable curl');
});
