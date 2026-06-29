/**
 * Presentation key for Garmin's per-night HRV status chip.
 *
 * Returns a title-cased status key (e.g. "Unbalanced") for a present status, or `null` when
 * the status should not surface a chip. The backend normalizes an absent Garmin status
 * (`none`/null) to the literal string "Unknown" — `DailyHrvStats.status` is never null once a
 * night has an HRV summary — so "Unknown" is treated as absent here too. That keeps the chip
 * hidden for status-less nights, matching the design spec's "Garmin status absent: chip hidden"
 * edge case rather than rendering a meaningless "Garmin: Unknown".
 */
export function garminStatusKey(status: string | null | undefined): string | null {
	if (!status) return null;
	const key = status.charAt(0).toUpperCase() + status.slice(1).toLowerCase();
	return key === 'Unknown' ? null : key;
}
