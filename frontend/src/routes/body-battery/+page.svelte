<script lang="ts">
	import { onMount } from 'svelte';
	import {
		api,
		type BodyBatteryRawData,
		type BodyBatteryDaily,
		type BodyBatteryAnalysis
	} from '$lib/api';
	import { createDateLoader, startRealtimePage } from '$lib/realtime-page';
	import ChartCard from '$lib/components/ChartCard.svelte';
	import LineChart from '$lib/components/LineChart.svelte';
	import MetricPageHeader from '$lib/components/MetricPageHeader.svelte';
	import PageState from '$lib/components/PageState.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import DateSelector from '$lib/components/DateSelector.svelte';
	import { type TrendRange, filterByRange, PERIOD_KEY_MAP } from '$lib/trend-range';
	import { fmt } from '$lib/format';
	import { COLORS, withAlpha } from '$lib/colors';
	import { chartTooltip, DARK_GRID, DARK_GRID_Y, DARK_BORDER, DARK_TICK } from '$lib/chart-setup';
	import type { ChartConfiguration } from 'chart.js';

	let agg: BodyBatteryDaily | null = $state(null);
	let analysis: BodyBatteryAnalysis | null = $state(null);
	let intradayData: BodyBatteryRawData | null = $state(null);
	let selectedDate = $state('');
	let trendRange: TrendRange = $state('3M');
	let loading = $state(true);
	let error: string | null = $state(null);

	async function fetchData() {
		const [nextAgg, nextAnalysis] = await Promise.all([
			api.getBodyBatteryDaily(),
			api.getBodyBatteryAnalysis()
		]);
		agg = nextAgg;
		analysis = nextAnalysis;
		const date = selectedDate;
		if (date) {
			const data = await api.getBodyBatteryRaw(date);
			if (selectedDate === date) {
				intradayData = data;
			}
		}
	}

	onMount(() => {
		return startRealtimePage({
			fetchData,
			setError: (message) => { error = message; },
			setLoading: (value) => { loading = value; }
		});
	});

	const onDateChange = createDateLoader<BodyBatteryRawData>({
		setSelectedDate: (date) => { selectedDate = date; },
		clearData: () => { intradayData = null; },
		fetchByDate: (date) => api.getBodyBatteryRaw(date),
		setData: (data) => { intradayData = data; },
		setError: (message) => { error = message; }
	});

	// ── Trend chart: daily min/max with 7d MA on min ──
	let trendConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!analysis) return null;
		const trend = filterByRange(analysis.trend, trendRange);
		return {
			type: 'line',
			data: {
				labels: trend.map(p => p.date),
				datasets: [
					{
						label: 'Daily Max',
						data: trend.map(p => p.max_val),
						borderColor: withAlpha(COLORS.bodyBattery, '40'),
						borderWidth: 1,
						borderDash: [4, 4],
						pointRadius: 0,
						tension: 0.3,
						spanGaps: false,
						fill: false
					},
					{
						label: 'Daily Min',
						data: trend.map(p => p.min_val),
						borderColor: withAlpha(COLORS.bodyBattery, '50'),
						borderWidth: 1,
						pointRadius: 1.5,
						pointBackgroundColor: withAlpha(COLORS.bodyBattery, '60'),
						tension: 0.3,
						spanGaps: false,
						fill: '-1',
						backgroundColor: withAlpha(COLORS.bodyBattery, '08')
					},
					{
						label: '7d Avg (Min)',
						data: trend.map(p => p.ma7_min),
						borderColor: COLORS.bodyBattery,
						borderWidth: 2.5,
						pointRadius: 0,
						tension: 0.35,
						spanGaps: false,
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
					tooltip: chartTooltip(withAlpha(COLORS.bodyBattery, '60'))
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
						title: { display: true, text: 'battery %', ...DARK_TICK },
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
						data: boxes.map(b => b.max_val),
						borderColor: withAlpha(COLORS.bodyBattery, '30'),
						borderWidth: 1,
						borderDash: [3, 3],
						pointRadius: 0,
						tension: 0.3,
						fill: false
					},
					{
						label: 'Q3',
						data: boxes.map(b => b.q3_val),
						borderColor: withAlpha(COLORS.bodyBattery, '50'),
						borderWidth: 1,
						pointRadius: 0,
						tension: 0.3,
						fill: false
					},
					{
						label: 'Median',
						data: boxes.map(b => b.median_val),
						borderColor: COLORS.bodyBattery,
						borderWidth: 2.5,
						pointRadius: 0,
						tension: 0.3,
						fill: '-1',
						backgroundColor: withAlpha(COLORS.bodyBattery, '15')
					},
					{
						label: 'Q1',
						data: boxes.map(b => b.q1_val),
						borderColor: withAlpha(COLORS.bodyBattery, '50'),
						borderWidth: 1,
						pointRadius: 0,
						tension: 0.3,
						fill: '-1',
						backgroundColor: withAlpha(COLORS.bodyBattery, '10')
					},
					{
						label: 'Min',
						data: boxes.map(b => b.min_val),
						borderColor: withAlpha(COLORS.bodyBattery, '30'),
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
					tooltip: chartTooltip(withAlpha(COLORS.bodyBattery, '60'))
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
						title: { display: true, text: 'battery %', ...DARK_TICK },
						ticks: DARK_TICK,
						grid: DARK_GRID_Y,
						border: DARK_BORDER
					}
				}
			}
		};
	});

	// ── Intraday body battery ──
	let intradayConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!intradayData || intradayData.body_battery.length === 0) return null;
		return {
			type: 'line',
			data: {
				labels: intradayData.body_battery.map(d => d.timestamp),
				datasets: [{
					label: 'Body Battery',
					data: intradayData.body_battery.map(d => d.value),
					borderColor: COLORS.bodyBattery,
					borderWidth: 1.5,
					pointRadius: 0,
					tension: 0.2,
					fill: { target: 'origin', above: withAlpha(COLORS.bodyBattery, '10') }
				}]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: false },
					tooltip: chartTooltip(withAlpha(COLORS.bodyBattery, '60'))
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
						title: { display: true, text: 'battery %', ...DARK_TICK },
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
		const bb = pw;
		return {
			avgMin: bb.avg_min,
			avgMax: bb.avg_max,
			days: bb.days_tracked
		};
	});
</script>

<svelte:head><title>Body Battery - Garmin Stats</title></svelte:head>

<PageState error={agg ? null : error} {loading}>
	{#if agg}
		{#if error}
			<div class="mb-4 flex items-center justify-between gap-3 rounded-lg border border-[rgba(232,93,74,0.3)] bg-[rgba(232,93,74,0.08)] p-3">
				<p class="text-[#E85D4A]">Error: {error}</p>
				<button type="button" class="shrink-0 text-[#E85D4A] opacity-70 hover:opacity-100" onclick={() => (error = null)} aria-label="Dismiss error">✕</button>
			</div>
		{/if}
		<MetricPageHeader title="Body Battery" bind:trendRange />

		<DateSelector days={agg.days} selected={selectedDate} onchange={onDateChange} />

		{#if stats}
			<div class="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
				<StatCard title="Avg Daily Min" value={fmt(stats.avgMin)} unit="%" color={COLORS.heartRate} />
				<StatCard title="Avg Daily Max" value={fmt(stats.avgMax)} unit="%" color={COLORS.bodyBattery} />
				<StatCard title="Days Tracked" value={stats.days} color="#8a9baa" />
			</div>
		{/if}

		<ChartCard
			title="Body Battery Trend"
			footnote={trendConfig ? 'Bold line = 7-day moving average of daily min · Shaded area = daily min-max range' : ''}
		>
			{#if trendConfig}
				<LineChart config={trendConfig} height={300} />
			{/if}
		</ChartCard>

		{#if boxplotConfig}
			<ChartCard title="Weekly Spread (Daily Min)" footnote="Shaded band = middle 50% · Dashes = extremes · Bold = median">
				<LineChart config={boxplotConfig} height={260} />
			</ChartCard>
		{/if}

		{#if selectedDate && intradayConfig}
			<ChartCard title={`Intraday — ${selectedDate}`} footnote={`${intradayData?.body_battery.length ?? 0} readings`}>
				<LineChart config={intradayConfig} height={300} />
			</ChartCard>
		{:else if selectedDate}
			<div class="text-sm text-[#5e7282]">Loading intraday data...</div>
		{/if}
	{/if}
</PageState>
