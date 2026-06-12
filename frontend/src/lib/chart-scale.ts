/**
 * Tight linear-axis scaling for charts whose values sit in a small, known band
 * (e.g. robust-z recovery scores that rarely exceed ±3).
 *
 * Default auto-ranging overshoots to round bounds (a [-2, 1.3] series gets a
 * [-3, 2] axis), which flattens the signal. Instead, hug the data: bounds =
 * [min - pad, max + pad], and place ticks ONLY at round (half-integer) values
 * that fall inside — never at the padded extremes, which carry no information
 * and can be inferred from context.
 */

export interface TightScale {
	min: number;
	max: number;
	/** Round (half-integer) tick values strictly inside the padded bounds. */
	ticks: number[];
}

/**
 * @param values  the series values (nulls/non-finite ignored)
 * @param pad     margin added beyond min/max so the line is not clipped
 * @param step    tick spacing (0.5 = half-integers, 1 = integers)
 */
export function tightScale(
	values: ReadonlyArray<number | null | undefined>,
	pad = 0.1,
	step = 0.5
): TightScale | null {
	const finite = values.filter((v): v is number => v != null && Number.isFinite(v));
	if (finite.length === 0) return null;

	const min = Math.min(...finite) - pad;
	const max = Math.max(...finite) + pad;

	// First round tick at or above the lower bound, then step up while inside.
	const ticks: number[] = [];
	const first = Math.ceil(min / step) * step;
	for (let t = first; t <= max + 1e-9; t += step) {
		ticks.push(Math.round(t / step) * step);
	}
	return { min, max, ticks };
}
