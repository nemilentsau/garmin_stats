/** Format a nullable number for display. Integers get locale formatting, floats get 1 decimal. */
export function fmt(n: number | null | undefined): string {
	if (n == null) return '-';
	return Number.isInteger(n) ? n.toLocaleString() : n.toFixed(1);
}
