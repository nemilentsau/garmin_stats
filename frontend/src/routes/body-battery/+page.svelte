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
	import { dailyTrendConfig, simpleIntradayLineConfig, weeklyRibbonConfig } from '$lib/chart-options';
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
		return dailyTrendConfig({
			labels: trend.map(p => p.date),
			color: COLORS.bodyBattery,
			yTitle: 'battery %',
			beginAtZero: true,
			max: 100,
			daily: { label: 'Daily Min', values: trend.map(p => p.min_val) },
			movingAverage: { label: '7d Avg (Min)', values: trend.map(p => p.ma7_min) },
			dailyFill: { backgroundColor: withAlpha(COLORS.bodyBattery, '08') },
			extraDatasetsPosition: 'before',
			extraDatasets: [
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
				}
			]
		});
	});

	// ── Weekly boxplot ──
	let boxplotConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!analysis || analysis.weekly_boxplots.length === 0) return null;
		const boxes = analysis.weekly_boxplots;
		return weeklyRibbonConfig({
			labels: boxes.map(b => b.iso_week),
			max: boxes.map(b => b.max_val),
			q3: boxes.map(b => b.q3_val),
			median: boxes.map(b => b.median_val),
			q1: boxes.map(b => b.q1_val),
			min: boxes.map(b => b.min_val),
			color: COLORS.bodyBattery,
			yTitle: 'battery %',
			beginAtZero: true,
			yMax: 100
		});
	});

	// ── Intraday body battery ──
	// NOTE: migrating to simpleIntradayLineConfig intentionally fixes a drift —
	// the hand-written config here previously omitted `interaction: { mode:
	// 'index', intersect: false }` that every other intraday chart has.
	let intradayConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!intradayData || intradayData.body_battery.length === 0) return null;
		return simpleIntradayLineConfig({
			label: 'Body Battery',
			color: COLORS.bodyBattery,
			yTitle: 'battery %',
			labels: intradayData.body_battery.map(d => d.timestamp),
			values: intradayData.body_battery.map(d => d.value),
			beginAtZero: true,
			max: 100
		});
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

<PageState {error} {loading}>
	{#if agg}
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
