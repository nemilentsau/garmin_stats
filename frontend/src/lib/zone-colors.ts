/** Shared heart-rate zone color ramp (Z1-Z5, gray to red) for run detail views. */
export const ZONE_COLORS = ['#5e7282', '#4A90D9', '#4CAF82', '#D4944C', '#E85D4A'];

/** Color for a 1-indexed heart-rate zone, falling back to Z1 for out-of-range input. */
export function zoneColor(zone: number): string {
	return ZONE_COLORS[zone - 1] ?? ZONE_COLORS[0];
}
