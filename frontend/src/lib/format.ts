/** Format a nullable number for display. Integers get locale formatting, floats get 1 decimal. */
export function fmt(n: number | null | undefined): string {
	if (n == null) return '-';
	return Number.isInteger(n) ? n.toLocaleString() : n.toFixed(1);
}

/** Format a number with explicit sign (+/-), to `digits` decimal places (default 1). */
export function fmtSigned(n: number | null | undefined, digits = 1): string {
	if (n == null) return '-';
	// Decide the sign from the value AFTER rounding to `digits`, not the raw input: a tiny
	// negative that rounds to zero at this precision (e.g. -0.04 at 1dp) is zero, so it must
	// read "0.0", never a signed "-0.0". `Number(...)` collapses "-0.0" so the prefix check is
	// on a clean value; `toFixed` then re-pads the decimals (e.g. 2 → "2.0").
	const rounded = Number(n.toFixed(digits));
	const text = rounded.toFixed(digits);
	return rounded > 0 ? `+${text}` : text;
}
