export function localDateIso(date: Date = new Date()): string {
	const year = date.getFullYear();
	const month = String(date.getMonth() + 1).padStart(2, '0');
	const day = String(date.getDate()).padStart(2, '0');
	return `${year}-${month}-${day}`;
}

export function isIsoDateString(value: string): boolean {
	return /^\d{4}-\d{2}-\d{2}$/.test(value);
}

export function parseIsoDate(isoDate: string): Date {
	const [year, month, day] = isoDate.split('-').map(Number);
	return new Date(year, month - 1, day, 12, 0, 0, 0);
}

export function calendarDayDiff(startIsoDate: string, endIsoDate: string): number {
	const msPerDay = 24 * 60 * 60 * 1000;
	return Math.round((parseIsoDate(endIsoDate).getTime() - parseIsoDate(startIsoDate).getTime()) / msPerDay);
}

export function addDays(isoDate: string, delta: number): string {
	const next = parseIsoDate(isoDate);
	next.setDate(next.getDate() + delta);
	return localDateIso(next);
}

export function elapsedDaysInWindow(
	startIsoDate: string,
	currentIsoDate: string,
	plannedDays: number
): number {
	return Math.max(0, Math.min(calendarDayDiff(startIsoDate, currentIsoDate) + 1, plannedDays));
}

// Shared display formatters (Intl instances created once, not per render).
const _fullDate = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
const _dayMonth = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' });
const _weekdayDayMonth = new Intl.DateTimeFormat('en-US', { weekday: 'short', month: 'short', day: 'numeric' });

/** "Jun 5, 2026" */
export function fmtFullDate(date: Date): string {
	return _fullDate.format(date);
}

/** "Jun 5" */
export function fmtDayMonth(date: Date): string {
	return _dayMonth.format(date);
}

/** "Thu, Jun 5" */
export function fmtWeekdayDayMonth(date: Date): string {
	return _weekdayDayMonth.format(date);
}
