/**
 * Shared display formatters for the run pages (`/runs` list + `/runs/[id]` detail).
 * Pure formatting only — every value is already computed by the backend, already in
 * US imperial units (mi, min/mi, ft, °F — CLAUDE.md units rule); nothing here derives,
 * aggregates, smooths, or converts units. Kept in one place so the list and detail pages
 * can never drift apart on how a pace or duration reads.
 */

/** Distance in miles, 2 decimals. */
export function fmtMi(distanceMi: number | null): string {
	return distanceMi == null ? '—' : distanceMi.toFixed(2);
}

/** Seconds -> h:mm:ss, with the hour segment dropped under 1h (m:ss). */
export function fmtDuration(seconds: number | null): string {
	if (seconds == null) return '—';
	const total = Math.round(seconds);
	const h = Math.floor(total / 3600);
	const m = Math.floor((total % 3600) / 60);
	const s = total % 60;
	const pad = (n: number) => String(n).padStart(2, '0');
	return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

/** Pace in min/mi -> m:ss (minutes not zero-padded). */
export function fmtPace(paceMinPerMi: number | null): string {
	if (paceMinPerMi == null) return '—';
	const totalSeconds = Math.round(paceMinPerMi * 60);
	const m = Math.floor(totalSeconds / 60);
	const s = totalSeconds % 60;
	return `${m}:${String(s).padStart(2, '0')}`;
}

/** Feet, whole number with thousands separator. */
export function fmtFt(feet: number | null): string {
	return feet == null ? '—' : Math.round(feet).toLocaleString();
}

/** Fahrenheit, 1 decimal. */
export function fmtF(temperatureF: number | null): string {
	return temperatureF == null ? '—' : temperatureF.toFixed(1);
}

/** Miles per hour, 1 decimal. */
export function fmtMph(speedMph: number | null): string {
	return speedMph == null ? '—' : speedMph.toFixed(1);
}

/** Centimeters, 1 decimal. */
export function fmtCm(centimeters: number | null): string {
	return centimeters == null ? '—' : centimeters.toFixed(1);
}

/** ISO local timestamp -> "HH:MM". */
export function fmtStartTime(startTimeLocal: string): string {
	return startTimeLocal.slice(11, 16);
}

export function fmtLoad(load: number | null): string {
	return load == null ? '—' : Math.round(load).toLocaleString();
}

export function fmtTE(te: number | null): string {
	return te == null ? '—' : te.toFixed(1);
}

/** Chest strap ("CHEST") vs wrist ("WRIST") HR-source badge label, or null for unknown sources. */
export function hrBadgeLabel(source: string | null): string | null {
	if (source === 'strap') return 'CHEST';
	if (source === 'wrist') return 'WRIST';
	return null;
}
