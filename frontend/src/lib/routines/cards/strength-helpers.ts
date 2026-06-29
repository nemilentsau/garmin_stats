/**
 * Pure helpers for StrengthSessionCard.
 *
 * Extracted so they can be unit-tested independently of Svelte runes. The component owns
 * mutable $state; these helpers only build initial values from prescribed + persisted actual
 * and serialize live state to the StrengthActual wire shape (with NaN coercion).
 */

export type StrengthSetLog = {
	set_index: number;
	weight: number | null;
	reps: number | null;
	rir: number | null;
};

export type LoggedStrengthExercise = {
	exercise_id: string | null;
	label: string | null;
	is_extra: boolean;
	sets: StrengthSetLog[];
};

export type PrescribedExercise = {
	id: string;
	label: string;
	set_scheme?: string | null;
	detail?: string | null;
};

export type RatingPrompt = {
	key: string;
	label: string;
	scale_min: number;
	scale_max: number;
};

export type ExistingActual = {
	card_type: 'strength_session';
	exercises: LoggedStrengthExercise[];
	ratings?: Record<string, number>;
};

/**
 * Build the initial exercises array for the log state.
 *
 * When an existingActual is present: restore all exercises (prescribed + extras) from it,
 * preserving set values, is_extra, and labels. When absent: pre-seed one empty set per
 * prescribed exercise (no extras).
 */
export function buildInitialExercises(
	prescribed: PrescribedExercise[],
	existingActual: ExistingActual | null
): LoggedStrengthExercise[] {
	if (existingActual) {
		return existingActual.exercises.map((ex) => ({
			exercise_id: ex.exercise_id,
			label: ex.label,
			is_extra: ex.is_extra,
			sets: ex.sets.map((s) => ({
				set_index: s.set_index,
				weight: s.weight,
				reps: s.reps,
				rir: s.rir
			}))
		}));
	}
	return prescribed.map((ex) => ({
		exercise_id: ex.id,
		label: ex.label,
		is_extra: false,
		sets: [{ set_index: 0, weight: null, reps: null, rir: null }]
	}));
}

/**
 * Build the initial ratings map for the log state.
 *
 * Fills every prompt key — from the saved actual when available, otherwise null.
 */
export function buildInitialRatings(
	prompts: RatingPrompt[],
	existingActual: ExistingActual | null
): Record<string, number | null> {
	const result: Record<string, number | null> = {};
	for (const p of prompts) {
		result[p.key] = existingActual?.ratings?.[p.key] ?? null;
	}
	return result;
}

/**
 * Coerce a single set's numeric fields: NaN (from an empty `<input type=number>`) → null.
 * Returns a new object conforming to the `number | null` contract of StrengthSetLog.
 */
export function coerceSet(s: StrengthSetLog): StrengthSetLog {
	return {
		set_index: s.set_index,
		weight: Number.isFinite(s.weight) ? s.weight : null,
		reps: Number.isFinite(s.reps) ? s.reps : null,
		rir: Number.isFinite(s.rir) ? s.rir : null
	};
}

/**
 * Serialize live exercises state to the wire shape, applying NaN coercion to all set fields.
 */
export function serializeExercises(exercises: LoggedStrengthExercise[]): LoggedStrengthExercise[] {
	return exercises.map((ex) => ({
		exercise_id: ex.exercise_id,
		label: ex.label,
		is_extra: ex.is_extra,
		sets: ex.sets.map(coerceSet)
	}));
}
