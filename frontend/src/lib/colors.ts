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
	// Running detail page (per-metric identity, distinct from the wellness hues above)
	pace: '#4FA8DE',
	elevation: '#B98D5B',
	cadence: '#7FBF6B',
	strideLength: '#5BC8C8',
	power: '#C15FA0',
	verticalOscillation: '#8E97D9',
	verticalRatio: '#D96B6B',
	groundContactTime: '#6BA88E',
	groundContactBalance: '#D9A73A',
	temperature: '#D98A4A',
	stamina: '#3DBF8F',
	staminaPotential: '#8FE0C4',
	performanceCondition: '#9B6BCD',
	runSpan: '#4CAF82',
	walkSpan: '#D4944C',
	standSpan: '#5e7282',
	// Route map pace quantile colors (fastest to slowest, warm to cool)
	paceQuantile2: '#DB8248',
	paceQuantile4: '#7FA3C9',
} as const;

/** Append hex alpha to a color string. */
export function withAlpha(color: string, alpha: string): string {
	return color + alpha;
}

/** Muted gray used for legend labels and the neutral insight-level fallback. */
export const DARK_MUTED_TEXT = '#8a9baa';

/** Map insight severity level to a display color. */
export function insightLevelColor(level: string): string {
	if (level === 'warning') return COLORS.heartRate;
	if (level === 'caution') return COLORS.stress;
	if (level === 'good') return COLORS.heartRateResting;
	return DARK_MUTED_TEXT;
}
