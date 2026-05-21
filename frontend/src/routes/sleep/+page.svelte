<script lang="ts">
	import { onMount } from 'svelte';
	import {
		api,
		type SleepDaily,
		type SleepData,
		type SleepAnalysis
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

	let agg: SleepDaily | null = $state(null);
	let analysis: SleepAnalysis | null = $state(null);
	let intradayData: SleepData | null = $state(null);
	let selectedDate = $state('');
	let trendRange: TrendRange = $state('3M');
	let loading = $state(true);
	let error: string | null = $state(null);

	async function fetchData() {
		const [nextAgg, nextAnalysis] = await Promise.all([
			api.getSleepDaily(),
			api.getSleepAnalysis()
		]);
		agg = nextAgg;
		analysis = nextAnalysis;
		if (selectedDate) {
			const data = await api.getSleepRaw(selectedDate);
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

	const onDateChange = createDateLoader<SleepData>({
		setSelectedDate: (date) => { selectedDate = date; },
		clearData: () => { intradayData = null; },
		fetchByDate: (date) => api.getSleepRaw(date),
		setData: (data) => { intradayData = data; },
		setError: (message) => { error = message; }
	});

	// ── Trend chart: score with 7d MA from analysis endpoint ──
	let trendConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!analysis) return null;
		const trend = filterByRange(analysis.score_trend, trendRange);
		return {
			type: 'line',
			data: {
				labels: trend.map(p => p.date),
				datasets: [
					{
						label: 'Sleep Score',
						data: trend.map(p => p.score),
						borderColor: withAlpha(COLORS.sleep, '50'),
						borderWidth: 1,
						pointRadius: 1.5,
						pointBackgroundColor: withAlpha(COLORS.sleep, '60'),
						tension: 0.3,
						spanGaps: true
					},
					{
						label: '7d Avg',
						data: trend.map(p => p.ma7),
						borderColor: COLORS.sleep,
						borderWidth: 2.5,
						pointRadius: 0,
						tension: 0.35,
						spanGaps: true
					},
					{
						label: 'Deep Score',
						data: trend.map(p => p.deep_score),
						borderColor: withAlpha(COLORS.sleep7Day, '60'),
						borderWidth: 1,
						borderDash: [4, 4],
						pointRadius: 0,
						tension: 0.3,
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
					tooltip: chartTooltip(withAlpha(COLORS.sleep, '60'))
				},
				scales: {
					x: {
						ticks: { maxRotation: 45, font: { size: 10 }, ...DARK_TICK },
						grid: DARK_GRID,
						border: DARK_BORDER
					},
					y: {
						beginAtZero: false,
						title: { display: true, text: 'score', ...DARK_TICK },
						ticks: DARK_TICK,
						grid: DARK_GRID_Y,
						border: DARK_BORDER
					}
				}
			}
		};
	});

	// ── Weekly boxplot as area chart ──
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
						data: boxes.map(b => b.max_score),
						borderColor: withAlpha(COLORS.sleep, '30'),
						borderWidth: 1,
						borderDash: [3, 3],
						pointRadius: 0,
						tension: 0.3,
						fill: false
					},
					{
						label: 'Q3',
						data: boxes.map(b => b.q3_score),
						borderColor: withAlpha(COLORS.sleep, '50'),
						borderWidth: 1,
						pointRadius: 0,
						tension: 0.3,
						fill: false
					},
					{
						label: 'Median',
						data: boxes.map(b => b.median_score),
						borderColor: COLORS.sleep,
						borderWidth: 2.5,
						pointRadius: 0,
						tension: 0.3,
						fill: '-1',
						backgroundColor: withAlpha(COLORS.sleep, '15')
					},
					{
						label: 'Q1',
						data: boxes.map(b => b.q1_score),
						borderColor: withAlpha(COLORS.sleep, '50'),
						borderWidth: 1,
						pointRadius: 0,
						tension: 0.3,
						fill: '-1',
						backgroundColor: withAlpha(COLORS.sleep, '10')
					},
					{
						label: 'Min',
						data: boxes.map(b => b.min_score),
						borderColor: withAlpha(COLORS.sleep, '30'),
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
					tooltip: chartTooltip(withAlpha(COLORS.sleep, '60'))
				},
				scales: {
					x: {
						ticks: { maxRotation: 45, font: { size: 10 }, ...DARK_TICK, maxTicksLimit: 12 },
						grid: DARK_GRID,
						border: DARK_BORDER
					},
					y: {
						beginAtZero: false,
						title: { display: true, text: 'score', ...DARK_TICK },
						ticks: DARK_TICK,
						grid: DARK_GRID_Y,
						border: DARK_BORDER
					}
				}
			}
		};
	});

	// ── Intraday: sleep stage chart ──
	let intradayConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!intradayData || intradayData.sleep_levels.length === 0) return null;
		const levels = intradayData.sleep_levels.filter(l => l.date === selectedDate);
		if (levels.length === 0) return null;
		const stageMap: Record<string, number> = { deep: 1, light: 2, rem: 3, awake: 4 };
		return {
			type: 'line',
			data: {
				labels: levels.map(l => l.timestamp),
				datasets: [{
					label: 'Sleep Stage',
					data: levels.map(l => stageMap[l.level] ?? 0),
					borderColor: COLORS.sleep,
					borderWidth: 1.5,
					pointRadius: 0,
					tension: 0,
					stepped: 'before' as const,
					fill: { target: 'origin', above: withAlpha(COLORS.sleep, '10') }
				}]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: false },
					tooltip: {
						...chartTooltip(withAlpha(COLORS.sleep, '60')),
						callbacks: {
							label: (ctx) => {
								const names: Record<number, string> = { 1: 'Deep', 2: 'Light', 3: 'REM', 4: 'Awake' };
								return names[ctx.parsed.y as number] ?? 'Unknown';
							}
						}
					}
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
						min: 0.5,
						max: 4.5,
						reverse: true,
						ticks: {
							...DARK_TICK,
							font: { size: 10 },
							stepSize: 1,
							callback: (value) => {
								const names: Record<number, string> = { 1: 'Deep', 2: 'Light', 3: 'REM', 4: 'Awake' };
								return names[Number(value)] ?? '';
							}
						},
						grid: DARK_GRID_Y,
						border: DARK_BORDER
					}
				}
			}
		};
	});

	// ── Assessment details for selected day ──
	let assessment = $derived.by(() => {
		if (!intradayData || intradayData.sleep_assessments.length === 0) return null;
		return intradayData.sleep_assessments.find(a => a.date === selectedDate) ?? intradayData.sleep_assessments[0];
	});

	let stats = $derived.by(() => {
		const pw = agg?.period_windows?.[PERIOD_KEY_MAP[trendRange]];
		if (!pw) return null;
		const s = pw;
		return {
			avg: s.avg_score,
			avgDeep: s.avg_deep_score,
			days: s.days_tracked
		};
	});
</script>

<svelte:head><title>Sleep - Garmin Stats</title></svelte:head>

<PageState {error} {loading}>
	{#if agg}
		<MetricPageHeader title="Sleep" bind:trendRange />

		<DateSelector days={agg.days} selected={selectedDate} onchange={onDateChange} />

		{#if stats}
			<div class="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
				<StatCard title="Avg Score" value={fmt(stats.avg)} unit="pts" color={COLORS.sleep} />
				<StatCard title="Avg Deep" value={fmt(stats.avgDeep)} unit="pts" color={COLORS.sleep7Day} />
				<StatCard title="Days Tracked" value={stats.days} color="#8a9baa" />
			</div>
		{/if}

		<ChartCard title="Sleep Score Trend" footnote={trendConfig ? 'Bold line = 7-day moving average · Dashed = deep sleep score' : ''}>
			{#if trendConfig}
				<LineChart config={trendConfig} height={300} />
			{/if}
		</ChartCard>

		{#if boxplotConfig}
			<ChartCard title="Weekly Spread" footnote="Shaded band = middle 50% of nights · Dashes = extremes · Bold = median">
				<LineChart config={boxplotConfig} height={260} />
			</ChartCard>
		{/if}

		{#if selectedDate && intradayConfig}
			<ChartCard
				title={`Sleep Stages — ${selectedDate}`}
				footnote={`${intradayData?.sleep_levels.filter((level) => level.date === selectedDate).length ?? 0} readings`}
			>
				<LineChart config={intradayConfig} height={260} />
			</ChartCard>

			{#if assessment}
				<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
					<StatCard title="Overall Score" value={fmt(assessment.overall_score)} color={COLORS.sleep} />
					<StatCard title="Deep Sleep" value={fmt(assessment.deep_sleep_score)} color={COLORS.sleep7Day} />
					<StatCard title="REM Sleep" value={fmt(assessment.rem_sleep_score)} color={COLORS.hrv} />
					<StatCard title="Awakenings" value={fmt(assessment.awakenings_count)} color={COLORS.stress} />
				</div>
			{/if}
		{:else if selectedDate}
			<div class="text-sm text-[#5e7282]">Loading intraday data...</div>
		{/if}
	{/if}
</PageState>
