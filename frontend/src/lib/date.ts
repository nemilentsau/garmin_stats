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
