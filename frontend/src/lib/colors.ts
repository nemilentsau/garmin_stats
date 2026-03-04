/** Centralized chart color palette. Each metric has a primary color and a faded variant for bands. */
export const COLORS = {
	heartRate: '#E85D4A',
	heartRateResting: '#4CAF82',
	stress: '#D4944C',
	bodyBattery: '#4CAF82',
	spo2: '#4A90D9',
	spo2Min: '#E85D4A',
	respiration: '#5BB5A6',
	hrv: '#9B6BCD',
	hrvWeekly: '#b794e0',
	sleep: '#6366B0',
	sleep7Day: '#8b8dd6',
	skinTemp: '#C9933A',
	skinTemp7Day: '#e0b35e',
	baseline: '#5e7282',
	zoneRest: '#4A6FA5',
} as const;

/** Append hex alpha to a color string. */
export function withAlpha(color: string, alpha: string): string {
	return color + alpha;
}

/** Map insight severity level to a display color. */
export function insightLevelColor(level: string): string {
	if (level === 'warning') return COLORS.heartRate;
	if (level === 'caution') return COLORS.stress;
	if (level === 'good') return COLORS.heartRateResting;
	return '#8a9baa';
}
