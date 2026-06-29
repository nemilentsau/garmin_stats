/** Format a nullable number for display. Integers get locale formatting, floats get 1 decimal. */
export function fmt(n: number | null | undefined): string {
	if (n == null) return '-';
	return Number.isInteger(n) ? n.toLocaleString() : n.toFixed(1);
}

/** Format a number with explicit sign (+/-), to `digits` decimal places (default 1). */
export function fmtSigned(n: number | null | undefined, digits = 1): string {
	if (n == null) return '-';
	const rounded = n.toFixed(digits);
	return n > 0 ? `+${rounded}` : rounded;
}

/** Format a time window from two ISO timestamps as HH:MM–HH:MM. */
export function fmtTimeWindow(start: string | null | undefined, end: string | null | undefined): string {
	if (!start || !end) return '-';
	return `${start.slice(11, 16)}–${end.slice(11, 16)}`;
}
