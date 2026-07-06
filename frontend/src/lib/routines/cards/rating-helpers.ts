/**
 * Shared rating-prompt helpers for card components (strength, meditation).
 *
 * Owns the two halves of rating state that every prompted card repeats: seeding
 * the editable map from a persisted actual, and serializing it back to the wire
 * shape. The backend contract types ratings as dict[str, int], so cleanRatings
 * enforces integers (finite check + round) at the serialization boundary — a
 * typed decimal must never 422 the whole log update.
 */

export type RatingPrompt = {
	key: string;
	label: string;
	scale_min: number;
	scale_max: number;
};

/**
 * Build the initial ratings map for log state: every prompt key present, filled
 * from the saved ratings when available, otherwise null.
 */
export function buildInitialRatings(
	prompts: RatingPrompt[],
	existing: Record<string, number> | null | undefined
): Record<string, number | null> {
	const result: Record<string, number | null> = {};
	for (const p of prompts) {
		result[p.key] = existing?.[p.key] ?? null;
	}
	return result;
}

/**
 * Serialize live ratings state to the wire shape: drop null/non-finite entries
 * and round the rest to integers (backend contract is dict[str, int]).
 */
export function cleanRatings(ratings: Record<string, number | null>): Record<string, number> {
	const clean: Record<string, number> = {};
	for (const [key, value] of Object.entries(ratings)) {
		if (typeof value === 'number' && Number.isFinite(value)) {
			clean[key] = Math.round(value);
		}
	}
	return clean;
}
