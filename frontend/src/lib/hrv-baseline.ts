export const HRV_BASELINE_WINDOWS = [30, 60, 90] as const;
export type HrvBaselineWindow = (typeof HRV_BASELINE_WINDOWS)[number];
export const DEFAULT_HRV_BASELINE_WINDOW: HrvBaselineWindow = 60;

export function isHrvBaselineWindow(value: number): value is HrvBaselineWindow {
	return HRV_BASELINE_WINDOWS.includes(value as HrvBaselineWindow);
}

export function coerceHrvBaselineWindow(
	value: string | number | null | undefined,
	fallback: HrvBaselineWindow = DEFAULT_HRV_BASELINE_WINDOW
): HrvBaselineWindow {
	const numeric = typeof value === 'number' ? value : Number(value);
	return isHrvBaselineWindow(numeric) ? numeric : fallback;
}
