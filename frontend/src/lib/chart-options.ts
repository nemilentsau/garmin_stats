import type { ChartConfiguration, ChartDataset } from 'chart.js';
import { chartTooltip, DARK_BORDER, DARK_GRID, DARK_GRID_Y, DARK_TICK } from '$lib/chart-setup';
import { withAlpha } from '$lib/colors';

export const darkLegend = {
	labels: { boxWidth: 12, font: { size: 11 }, color: '#8a9baa' }
} as const;

export function categoryXAxis(maxTicksLimit?: number) {
	return {
		ticks: { maxRotation: 45, font: { size: 10 }, ...DARK_TICK, ...(maxTicksLimit ? { maxTicksLimit } : {}) },
		grid: DARK_GRID,
		border: DARK_BORDER
	} as const;
}

export function timeXAxis() {
	return {
		type: 'time' as const,
		time: { unit: 'hour' as const, displayFormats: { hour: 'HH:mm' } },
		ticks: { font: { size: 10 }, ...DARK_TICK },
		grid: DARK_GRID,
		border: DARK_BORDER
	} as const;
}

export function metricYAxis(title: string, options: { beginAtZero?: boolean; min?: number; max?: number } = {}) {
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
	labels: string[];
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

export function weeklySpreadDatasets<T>(
	boxes: T[],
	color: string,
	fields: { max: keyof T; q3: keyof T; median: keyof T; q1: keyof T; min: keyof T }
): ChartDataset<'line'>[] {
	return [
		{
			label: 'Max',
			data: boxes.map((box) => box[fields.max] as number | null),
			borderColor: withAlpha(color, '30'),
			borderWidth: 1,
			borderDash: [3, 3],
			pointRadius: 0,
			tension: 0.3,
			fill: false
		},
		{
			label: 'Q3',
			data: boxes.map((box) => box[fields.q3] as number | null),
			borderColor: withAlpha(color, '50'),
			borderWidth: 1,
			pointRadius: 0,
			tension: 0.3,
			fill: false
		},
		{
			label: 'Median',
			data: boxes.map((box) => box[fields.median] as number | null),
			borderColor: color,
			borderWidth: 2.5,
			pointRadius: 0,
			tension: 0.3,
			fill: '-1',
			backgroundColor: withAlpha(color, '15')
		},
		{
			label: 'Q1',
			data: boxes.map((box) => box[fields.q1] as number | null),
			borderColor: withAlpha(color, '50'),
			borderWidth: 1,
			pointRadius: 0,
			tension: 0.3,
			fill: '-1',
			backgroundColor: withAlpha(color, '10')
		},
		{
			label: 'Min',
			data: boxes.map((box) => box[fields.min] as number | null),
			borderColor: withAlpha(color, '30'),
			borderWidth: 1,
			borderDash: [3, 3],
			pointRadius: 0,
			tension: 0.3,
			fill: false
		}
	];
}
