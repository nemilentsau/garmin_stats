import type { ChartConfiguration, ChartDataset } from 'chart.js';
import { chartTooltip, DARK_BORDER, DARK_GRID, DARK_GRID_Y, DARK_TICK } from '$lib/chart-setup';
import { DARK_MUTED_TEXT, withAlpha } from '$lib/colors';

const darkLegend = {
	labels: { boxWidth: 12, font: { size: 11 }, color: DARK_MUTED_TEXT }
} as const;

function categoryXAxis(maxTicksLimit?: number) {
	return {
		ticks: { maxRotation: 45, font: { size: 10 }, ...DARK_TICK, ...(maxTicksLimit ? { maxTicksLimit } : {}) },
		grid: DARK_GRID,
		border: DARK_BORDER
	} as const;
}

function timeXAxis() {
	return {
		type: 'time' as const,
		time: { unit: 'hour' as const, displayFormats: { hour: 'HH:mm' } },
		ticks: { font: { size: 10 }, ...DARK_TICK },
		grid: DARK_GRID,
		border: DARK_BORDER
	} as const;
}

function metricYAxis(title: string, options: { beginAtZero?: boolean; min?: number; max?: number } = {}) {
	return {
		...options,
		title: { display: true, text: title, ...DARK_TICK },
		ticks: DARK_TICK,
		grid: DARK_GRID_Y,
		border: DARK_BORDER
	} as const;
}

export function darkLineOptions(args: {
	color: string;
	yTitle: string;
	beginAtZero?: boolean;
	min?: number;
	max?: number;
	xMaxTicksLimit?: number;
	showLegend?: boolean;
	timeAxis?: boolean;
}): NonNullable<ChartConfiguration<'line'>['options']> {
	return {
		responsive: true,
		maintainAspectRatio: false,
		interaction: { mode: 'index', intersect: false },
		plugins: {
			legend: args.showLegend === false ? { display: false } : darkLegend,
			tooltip: chartTooltip(withAlpha(args.color, '60'))
		},
		scales: {
			x: args.timeAxis ? timeXAxis() : categoryXAxis(args.xMaxTicksLimit),
			y: metricYAxis(args.yTitle, {
				beginAtZero: args.beginAtZero,
				min: args.min,
				max: args.max
			})
		}
	};
}

export function simpleIntradayLineConfig(args: {
	label: string;
	color: string;
	yTitle: string;
	labels: Array<string | null>;
	values: Array<number | null>;
	beginAtZero?: boolean;
	min?: number;
	max?: number;
}): ChartConfiguration<'line'> | null {
	if (args.labels.length === 0 || args.values.length === 0) return null;
	return {
		type: 'line',
		data: {
			labels: args.labels,
			datasets: [
				{
					label: args.label,
					data: args.values,
					borderColor: args.color,
					borderWidth: 1.5,
					pointRadius: 0,
					tension: 0.2,
					fill: { target: 'origin', above: withAlpha(args.color, '10') }
				}
			]
		},
		options: darkLineOptions({
			color: args.color,
			yTitle: args.yTitle,
			beginAtZero: args.beginAtZero,
			min: args.min,
			max: args.max,
			showLegend: false,
			timeAxis: true
		})
	};
}

/**
 * Weekly five-number-summary "ribbon" (Max/Q3/Median/Q1/Min) shared by the
 * stress/sleep/body-battery weekly-spread charts. Dataset shape and the
 * options block are identical across those pages; only the extracted value
 * arrays, color token, and y-axis title/bounds differ per metric.
 */
export function weeklyRibbonConfig(args: {
	labels: Array<string>;
	max: Array<number | null>;
	q3: Array<number | null>;
	median: Array<number | null>;
	q1: Array<number | null>;
	min: Array<number | null>;
	color: string;
	yTitle: string;
	beginAtZero?: boolean;
	yMax?: number;
}): ChartConfiguration<'line'> | null {
	if (args.labels.length === 0) return null;
	return {
		type: 'line',
		data: {
			labels: args.labels,
			datasets: [
				{
					label: 'Max',
					data: args.max,
					borderColor: withAlpha(args.color, '30'),
					borderWidth: 1,
					borderDash: [3, 3],
					pointRadius: 0,
					tension: 0.3,
					fill: false
				},
				{
					label: 'Q3',
					data: args.q3,
					borderColor: withAlpha(args.color, '50'),
					borderWidth: 1,
					pointRadius: 0,
					tension: 0.3,
					fill: false
				},
				{
					label: 'Median',
					data: args.median,
					borderColor: args.color,
					borderWidth: 2.5,
					pointRadius: 0,
					tension: 0.3,
					fill: '-1',
					backgroundColor: withAlpha(args.color, '15')
				},
				{
					label: 'Q1',
					data: args.q1,
					borderColor: withAlpha(args.color, '50'),
					borderWidth: 1,
					pointRadius: 0,
					tension: 0.3,
					fill: '-1',
					backgroundColor: withAlpha(args.color, '10')
				},
				{
					label: 'Min',
					data: args.min,
					borderColor: withAlpha(args.color, '30'),
					borderWidth: 1,
					borderDash: [3, 3],
					pointRadius: 0,
					tension: 0.3,
					fill: false
				}
			]
		},
		options: darkLineOptions({
			color: args.color,
			yTitle: args.yTitle,
			beginAtZero: args.beginAtZero,
			max: args.yMax,
			xMaxTicksLimit: 12
		})
	};
}

/**
 * Daily-value-with-7-day-moving-average trend line shared by the
 * stress/sleep/body-battery trend charts. The daily and moving-average
 * dataset styling is identical across those pages; `dailyFill` and
 * `extraDatasets` let a page preserve its own additional series (e.g.
 * sleep's dashed deep-sleep-score line, body battery's daily-max band)
 * without normalizing them away.
 */
export function dailyTrendConfig(args: {
	labels: Array<string>;
	color: string;
	yTitle: string;
	daily: { label: string; values: Array<number | null> };
	movingAverage: { label: string; values: Array<number | null> };
	beginAtZero?: boolean;
	min?: number;
	max?: number;
	dailyFill?: { backgroundColor: string };
	extraDatasets?: Array<ChartDataset<'line'>>;
	extraDatasetsPosition?: 'before' | 'after';
}): ChartConfiguration<'line'> {
	const dailyDataset: ChartDataset<'line'> = {
		label: args.daily.label,
		data: args.daily.values,
		borderColor: withAlpha(args.color, '50'),
		borderWidth: 1,
		pointRadius: 1.5,
		pointBackgroundColor: withAlpha(args.color, '60'),
		tension: 0.3,
		spanGaps: false,
		...(args.dailyFill
			? { fill: '-1' as const, backgroundColor: args.dailyFill.backgroundColor }
			: {})
	};
	const movingAverageDataset: ChartDataset<'line'> = {
		label: args.movingAverage.label,
		data: args.movingAverage.values,
		borderColor: args.color,
		borderWidth: 2.5,
		pointRadius: 0,
		tension: 0.35,
		spanGaps: false
	};
	const extra = args.extraDatasets ?? [];
	const datasets =
		args.extraDatasetsPosition === 'before'
			? [...extra, dailyDataset, movingAverageDataset]
			: [dailyDataset, movingAverageDataset, ...extra];
	return {
		type: 'line',
		data: { labels: args.labels, datasets },
		options: darkLineOptions({
			color: args.color,
			yTitle: args.yTitle,
			beginAtZero: args.beginAtZero,
			min: args.min,
			max: args.max
		})
	};
}
