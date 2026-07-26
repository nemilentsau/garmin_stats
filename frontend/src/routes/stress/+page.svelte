<script lang="ts">
	import { onMount } from 'svelte';
	import {
		api,
		type StressDaily,
		type StressRawData,
		type StressAnalysis
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
	import { COLORS } from '$lib/colors';
	import { dailyTrendConfig, simpleIntradayLineConfig, weeklyRibbonConfig } from '$lib/chart-options';
	import type { ChartConfiguration } from 'chart.js';

	let agg: StressDaily | null = $state(null);
	let analysis: StressAnalysis | null = $state(null);
	let intradayData: StressRawData | null = $state(null);
	let selectedDate = $state('');
	let trendRange: TrendRange = $state('3M');
	let loading = $state(true);
	let error: string | null = $state(null);

	async function fetchData() {
		const [nextAgg, nextAnalysis] = await Promise.all([
			api.getStressDaily(),
			api.getStressAnalysis()
		]);
		agg = nextAgg;
		analysis = nextAnalysis;
		const date = selectedDate;
		if (date) {
			const data = await api.getStressRaw(date);
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
		return dailyTrendConfig({
			labels: trend.map(p => p.date),
			color: COLORS.stress,
			yTitle: 'stress',
			beginAtZero: true,
			max: 100,
			daily: { label: 'Daily Avg', values: trend.map(p => p.avg) },
			movingAverage: { label: '7d Avg', values: trend.map(p => p.ma7) }
		});
	});

	// ── Weekly boxplot ──
	let boxplotConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!analysis || analysis.weekly_boxplots.length === 0) return null;
		const boxes = analysis.weekly_boxplots;
		return weeklyRibbonConfig({
			labels: boxes.map(b => b.iso_week),
			max: boxes.map(b => b.max_avg),
			q3: boxes.map(b => b.q3_avg),
			median: boxes.map(b => b.median_avg),
			q1: boxes.map(b => b.q1_avg),
			min: boxes.map(b => b.min_avg),
			color: COLORS.stress,
			yTitle: 'stress',
			beginAtZero: true,
			yMax: 100
		});
	});

	// ── Intraday stress ──
	// NOTE: migrating to simpleIntradayLineConfig intentionally fixes a drift —
	// the hand-written config here previously omitted `interaction: { mode:
	// 'index', intersect: false }` that every other intraday chart has.
	let intradayConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!intradayData || intradayData.stress.length === 0) return null;
		return simpleIntradayLineConfig({
			label: 'Stress',
			color: COLORS.stress,
			yTitle: 'stress',
			labels: intradayData.stress.map(d => d.timestamp),
			values: intradayData.stress.map(d => d.value),
			beginAtZero: true,
			max: 100
		});
	});

	let stats = $derived.by(() => {
		const pw = agg?.period_windows?.[PERIOD_KEY_MAP[trendRange]];
		if (!pw) return null;
		const s = pw;
		return {
			avg: s.avg,
			typicalLow: s.typical_low,
			typicalHigh: s.typical_high
		};
	});
</script>

<svelte:head><title>Stress - Garmin Stats</title></svelte:head>

<PageState {error} {loading}>
	{#if agg}
		<MetricPageHeader title="Stress" bind:trendRange />

		<DateSelector days={agg.days} selected={selectedDate} onchange={onDateChange} />

		{#if stats}
			<div class="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
				<StatCard title="Overall Avg" value={fmt(stats.avg)} color={COLORS.stress} />
				<StatCard title="Typical Low" value={fmt(stats.typicalLow)} color={COLORS.spo2} />
				<StatCard title="Typical High" value={fmt(stats.typicalHigh)} color={COLORS.heartRate} />
			</div>
		{/if}

		<ChartCard title="Stress Trend" footnote={trendConfig ? 'Bold line = 7-day moving average' : ''}>
			{#if trendConfig}
				<LineChart config={trendConfig} height={300} />
			{/if}
		</ChartCard>

		{#if boxplotConfig}
			<ChartCard title="Weekly Spread" footnote="Shaded band = middle 50% · Dashes = extremes · Bold = median">
				<LineChart config={boxplotConfig} height={260} />
			</ChartCard>
		{/if}

		{#if selectedDate && intradayConfig}
			<ChartCard title={`Intraday — ${selectedDate}`} footnote={`${intradayData?.stress.length ?? 0} readings`}>
				<LineChart config={intradayConfig} height={300} />
			</ChartCard>
		{:else if selectedDate}
			<div class="text-sm text-[#5e7282]">Loading intraday data...</div>
		{/if}
	{/if}
</PageState>
