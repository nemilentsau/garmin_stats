/** Shared trend-range utilities for time-window filtering across all tabs. */

export type TrendRange = '1M' | '3M' | '6M' | 'All';
export const TREND_RANGES: TrendRange[] = ['1M', '3M', '6M', 'All'];

/** Maps frontend range to backend pattern window key (1M floors to 3M). */
export const PERIOD_KEY_MAP: Record<TrendRange, string> = {
	'1M': '3M',
	'3M': '3M',
	'6M': '6M',
	'All': 'All'
};

/** Returns an ISO date string cutoff for the given range, or null for 'All'. */
export function trendCutoff(range: TrendRange): string | null {
	if (range === 'All') return null;
	const d = new Date();
	const months = range === '1M' ? 1 : range === '3M' ? 3 : 6;
	d.setMonth(d.getMonth() - months);
	return d.toISOString().slice(0, 10);
}

/** Filter items with a `date` field by the given trend range. */
export function filterByRange<T extends { date: string }>(items: T[], range: TrendRange): T[] {
	const cutoff = trendCutoff(range);
	if (!cutoff) return items;
	return items.filter((item) => item.date >= cutoff);
}
