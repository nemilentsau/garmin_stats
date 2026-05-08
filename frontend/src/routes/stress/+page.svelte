<script lang="ts">
	import { onMount } from 'svelte';
	import {
		api,
		type DailyAggregates,
		type StressRawData,
		type StressAnalysis
	} from '$lib/api';
	import { createDateLoader, startRealtimePage } from '$lib/realtime-page';
	import LineChart from '$lib/components/LineChart.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import DateSelector from '$lib/components/DateSelector.svelte';
	import TrendRangePicker from '$lib/components/TrendRangePicker.svelte';
	import { type TrendRange, filterByRange, PERIOD_KEY_MAP } from '$lib/trend-range';
	import { fmt } from '$lib/format';
	import { COLORS, withAlpha } from '$lib/colors';
	import { chartTooltip, DARK_GRID, DARK_GRID_Y, DARK_BORDER, DARK_TICK } from '$lib/chart-setup';
	import type { ChartConfiguration } from 'chart.js';

	let agg: DailyAggregates | null = $state(null);
	let analysis: StressAnalysis | null = $state(null);
	let intradayData: StressRawData | null = $state(null);
	let selectedDate = $state('');
	let trendRange: TrendRange = $state('3M');
	let loading = $state(true);
	let error: string | null = $state(null);

	async function fetchData() {
		const [nextAgg, nextAnalysis] = await Promise.all([
			api.getDailyAggregates(),
			api.getStressAnalysis()
		]);
		agg = nextAgg;
		analysis = nextAnalysis;
		if (selectedDate) {
			const data = await api.getStressRaw(selectedDate);
			intradayData = data;
		}
	}

	onMount(() => {
		return startRealtimePage({
			fetchData,
			setError: (message) => { error = message; },
			setLoading: (value) => { loading = value; }
		});
	});

	const onDateChange = createDateLoader<StressRawData>({
		setSelectedDate: (date) => { selectedDate = date; },
		clearData: () => { intradayData = null; },
		fetchByDate: (date) => api.getStressRaw(date),
		setData: (data) => { intradayData = data; },
		setError: (message) => { error = message; }
	});

	// ── Trend chart: daily avg with 7d MA ──
	let trendConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!analysis) return null;
		const trend = filterByRange(analysis.avg_trend, trendRange);
		return {
			type: 'line',
			data: {
				labels: trend.map(p => p.date),
				datasets: [
					{
						label: 'Daily Avg',
						data: trend.map(p => p.avg),
						borderColor: withAlpha(COLORS.stress, '50'),
						borderWidth: 1,
						pointRadius: 1.5,
						pointBackgroundColor: withAlpha(COLORS.stress, '60'),
						tension: 0.3,
						spanGaps: true
					},
					{
						label: '7d Avg',
						data: trend.map(p => p.ma7),
						borderColor: COLORS.stress,
						borderWidth: 2.5,
						pointRadius: 0,
						tension: 0.35,
						spanGaps: true
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				interaction: { mode: 'index' as const, intersect: false },
				plugins: {
					legend: { labels: { boxWidth: 12, font: { size: 11 }, color: '#8a9baa' } },
					tooltip: chartTooltip(withAlpha(COLORS.stress, '60'))
				},
				scales: {
					x: {
						ticks: { maxRotation: 45, font: { size: 10 }, ...DARK_TICK },
						grid: DARK_GRID,
						border: DARK_BORDER
					},
					y: {
						beginAtZero: true,
						max: 100,
						title: { display: true, text: 'stress', ...DARK_TICK },
						ticks: DARK_TICK,
						grid: DARK_GRID_Y,
						border: DARK_BORDER
					}
				}
			}
		};
	});

	// ── Weekly boxplot ──
	let boxplotConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!analysis || analysis.weekly_boxplots.length === 0) return null;
		const boxes = analysis.weekly_boxplots;
		return {
			type: 'line',
			data: {
				labels: boxes.map(b => b.iso_week),
				datasets: [
					{
						label: 'Max',
						data: boxes.map(b => b.max_avg),
						borderColor: withAlpha(COLORS.stress, '30'),
						borderWidth: 1,
						borderDash: [3, 3],
						pointRadius: 0,
						tension: 0.3,
						fill: false
					},
					{
						label: 'Q3',
						data: boxes.map(b => b.q3_avg),
						borderColor: withAlpha(COLORS.stress, '50'),
						borderWidth: 1,
						pointRadius: 0,
						tension: 0.3,
						fill: false
					},
					{
						label: 'Median',
						data: boxes.map(b => b.median_avg),
						borderColor: COLORS.stress,
						borderWidth: 2.5,
						pointRadius: 0,
						tension: 0.3,
						fill: '-1',
						backgroundColor: withAlpha(COLORS.stress, '15')
					},
					{
						label: 'Q1',
						data: boxes.map(b => b.q1_avg),
						borderColor: withAlpha(COLORS.stress, '50'),
						borderWidth: 1,
						pointRadius: 0,
						tension: 0.3,
						fill: '-1',
						backgroundColor: withAlpha(COLORS.stress, '10')
					},
					{
						label: 'Min',
						data: boxes.map(b => b.min_avg),
						borderColor: withAlpha(COLORS.stress, '30'),
						borderWidth: 1,
						borderDash: [3, 3],
						pointRadius: 0,
						tension: 0.3,
						fill: false
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				interaction: { mode: 'index' as const, intersect: false },
				plugins: {
					legend: { labels: { boxWidth: 12, font: { size: 11 }, color: '#8a9baa' } },
					tooltip: chartTooltip(withAlpha(COLORS.stress, '60'))
				},
				scales: {
					x: {
						ticks: { maxRotation: 45, font: { size: 10 }, ...DARK_TICK, maxTicksLimit: 12 },
						grid: DARK_GRID,
						border: DARK_BORDER
					},
					y: {
						beginAtZero: true,
						max: 100,
						title: { display: true, text: 'stress', ...DARK_TICK },
						ticks: DARK_TICK,
						grid: DARK_GRID_Y,
						border: DARK_BORDER
					}
				}
			}
		};
	});

	// ── Intraday stress ──
	let intradayConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!intradayData || intradayData.stress.length === 0) return null;
		return {
			type: 'line',
			data: {
				labels: intradayData.stress.map(d => d.timestamp),
				datasets: [{
					label: 'Stress',
					data: intradayData.stress.map(d => d.value),
					borderColor: COLORS.stress,
					borderWidth: 1.5,
					pointRadius: 0,
					tension: 0.2,
					fill: { target: 'origin', above: withAlpha(COLORS.stress, '10') }
				}]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: false },
					tooltip: chartTooltip(withAlpha(COLORS.stress, '60'))
				},
				scales: {
					x: {
						type: 'time',
						time: { unit: 'hour', displayFormats: { hour: 'HH:mm' } },
						ticks: { font: { size: 10 }, ...DARK_TICK },
						grid: DARK_GRID,
						border: DARK_BORDER
					},
					y: {
						beginAtZero: true,
						max: 100,
						title: { display: true, text: 'stress', ...DARK_TICK },
						ticks: DARK_TICK,
						grid: DARK_GRID_Y,
						border: DARK_BORDER
					}
				}
			}
		};
	});

	let stats = $derived.by(() => {
		const pw = agg?.period_windows?.[PERIOD_KEY_MAP[trendRange]];
		if (!pw) return null;
		const s = pw.stress;
		return {
			avg: s.avg,
			typicalLow: s.typical_low,
			typicalHigh: s.typical_high
		};
	});
</script>

<svelte:head><title>Stress - Garmin Stats</title></svelte:head>

{#if error}
	<div class="bg-[rgba(232,93,74,0.08)] border border-[rgba(232,93,74,0.3)] rounded-lg p-4">
		<p class="text-[#E85D4A]">Error: {error}</p>
	</div>
{:else if loading}
	<div class="flex items-center justify-center h-64">
		<div class="text-[#5e7282]">Loading...</div>
	</div>
{:else if agg}
	<div class="flex items-center justify-between mb-4">
		<h1 class="text-xl font-bold text-[#e8f0f5]">Stress</h1>
		<TrendRangePicker bind:value={trendRange} />
	</div>

	<DateSelector days={agg.days} selected={selectedDate} onchange={onDateChange} />

	{#if stats}
		<div class="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
			<StatCard title="Overall Avg" value={fmt(stats.avg)} colorClass="text-[{COLORS.stress}]" />
			<StatCard title="Typical Low" value={fmt(stats.typicalLow)} colorClass="text-[#4A90D9]" />
			<StatCard title="Typical High" value={fmt(stats.typicalHigh)} colorClass="text-[#E85D4A]" />
		</div>
	{/if}

	<div class="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-5 mb-6">
		<h2 class="text-sm font-semibold text-[#8a9baa] uppercase tracking-wide mb-3">Stress Trend</h2>
		{#if trendConfig}
			<LineChart config={trendConfig} height={300} />
			<p class="text-xs text-[#4a5c6a] mt-2">Bold line = 7-day moving average</p>
		{/if}
	</div>

	{#if boxplotConfig}
		<div class="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-5 mb-6">
			<h2 class="text-sm font-semibold text-[#8a9baa] uppercase tracking-wide mb-3">Weekly Spread</h2>
			<LineChart config={boxplotConfig} height={260} />
			<p class="text-xs text-[#4a5c6a] mt-2">Shaded band = middle 50% · Dashes = extremes · Bold = median</p>
		</div>
	{/if}

	{#if selectedDate && intradayConfig}
		<div class="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-5">
			<h2 class="text-sm font-semibold text-[#8a9baa] uppercase tracking-wide mb-3">
				Intraday — {selectedDate}
			</h2>
			<LineChart config={intradayConfig} height={300} />
			<p class="text-xs text-[#4a5c6a] mt-2">{intradayData?.stress.length ?? 0} readings</p>
		</div>
	{:else if selectedDate}
		<div class="text-sm text-[#5e7282]">Loading intraday data...</div>
	{/if}
{/if}
