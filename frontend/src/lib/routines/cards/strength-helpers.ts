/**
 * Pure helpers for StrengthSessionCard.
 *
 * Extracted so they can be unit-tested independently of Svelte runes. The component owns
 * mutable $state; these helpers only build initial values from prescribed + persisted actual
 * and serialize live state to the StrengthActual wire shape. Rating-prompt helpers are shared
 * with other cards in rating-helpers.ts.
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

export type ExistingActual = {
	card_type: 'strength_session';
	exercises: LoggedStrengthExercise[];
	ratings?: Record<string, number>;
};

function emptySet(): StrengthSetLog {
	return { set_index: 0, weight: null, reps: null, rir: null };
}

function seedFromPrescription(ex: PrescribedExercise): LoggedStrengthExercise {
	return { exercise_id: ex.id, label: ex.label, is_extra: false, sets: [emptySet()] };
}

/**
 * Build the initial exercises array for the log state.
 *
 * Rows follow the prescription order: each prescribed exercise appears once, restored from
 * the saved actual when it was logged, otherwise pre-seeded with one empty set — so
 * exercises added to the template after a log was first saved still show up. Logged rows
 * that are extras or no longer prescribed are appended after, preserving their data.
 */
export function buildInitialExercises(
	prescribed: PrescribedExercise[],
	existingActual: ExistingActual | null
): LoggedStrengthExercise[] {
	if (!existingActual) {
		return prescribed.map(seedFromPrescription);
	}
	const logged = existingActual.exercises.map((ex) => ({
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
	const loggedById = new Map(
		logged.filter((ex) => !ex.is_extra && ex.exercise_id).map((ex) => [ex.exercise_id, ex])
	);
	const result = prescribed.map((p) => loggedById.get(p.id) ?? seedFromPrescription(p));
	const placed = new Set(result);
	for (const ex of logged) {
		if (!placed.has(ex)) result.push(ex);
	}
	return result;
}

/**
 * Coerce a single set's numeric fields to the wire contract: NaN (from an empty
 * `<input type=number>`) → null, and fractional reps/RIR rounded to integers
 * (backend types them int). Weight stays fractional.
 */
export function coerceSet(s: StrengthSetLog): StrengthSetLog {
	return {
		set_index: s.set_index,
		weight: Number.isFinite(s.weight) ? s.weight : null,
		reps: coerceInt(s.reps),
		rir: coerceInt(s.rir)
	};
}

function coerceInt(value: number | null): number | null {
	return typeof value === 'number' && Number.isFinite(value) ? Math.round(value) : null;
}

/**
 * Serialize live exercises state to the wire shape, applying coercion to all set fields.
 */
export function serializeExercises(exercises: LoggedStrengthExercise[]): LoggedStrengthExercise[] {
	return exercises.map((ex) => ({
		exercise_id: ex.exercise_id,
		label: ex.label,
		is_extra: ex.is_extra,
		sets: ex.sets.map(coerceSet)
	}));
}
