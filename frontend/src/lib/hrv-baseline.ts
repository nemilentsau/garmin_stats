import type { components } from './api-types';

// The window type IS the backend contract (generated from the BaselineWindow enum). Tying to it
// means a backend change — a removed window or a moved set — surfaces here at type-check time
// instead of as a silently-omitted picker button or a `?baseline=` URL that coerces to the wrong
// window.
export type HrvBaselineWindow = components['schemas']['BaselineWindow'];

// Selectable windows. `satisfies` pins the literal list to the contract: if the enum drops or
// renumbers a window, this array stops type-checking until it is updated to match.
export const HRV_BASELINE_WINDOWS = [30, 60, 90] as const satisfies readonly HrvBaselineWindow[];

export const DEFAULT_HRV_BASELINE_WINDOW: HrvBaselineWindow = 60;

export function isHrvBaselineWindow(value: number): value is HrvBaselineWindow {
	return (HRV_BASELINE_WINDOWS as readonly number[]).includes(value);
}

export function coerceHrvBaselineWindow(
	value: string | number | null | undefined,
	fallback: HrvBaselineWindow = DEFAULT_HRV_BASELINE_WINDOW
): HrvBaselineWindow {
	const numeric = typeof value === 'number' ? value : Number(value);
	return isHrvBaselineWindow(numeric) ? numeric : fallback;
}
