/** Centralized chart color palette. Each metric has a primary color and a faded variant for bands. */
export const COLORS = {
	heartRate: '#dc2626',
	heartRateResting: '#16a34a',
	stress: '#ea580c',
	bodyBattery: '#059669',
	spo2: '#2563eb',
	spo2Min: '#dc2626',
	respiration: '#0d9488',
	hrv: '#7c3aed',
	hrvWeekly: '#a78bfa',
	sleep: '#4f46e5',
	sleep7Day: '#818cf8',
	skinTemp: '#d97706',
	skinTemp7Day: '#f59e0b',
	baseline: '#9ca3af',
} as const;

/** Append hex alpha to a color string. */
export function withAlpha(color: string, alpha: string): string {
	return color + alpha;
}
