<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type SpO2Daily, type SpO2RawData } from '$lib/api';
	import { createDateLoader, startRealtimePage } from '$lib/realtime-page';
	import ChartCard from '$lib/components/ChartCard.svelte';
	import LineChart from '$lib/components/LineChart.svelte';
	import MetricDefinition from '$lib/components/MetricDefinition.svelte';
	import MetricPageHeader from '$lib/components/MetricPageHeader.svelte';
	import PageState from '$lib/components/PageState.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import DateSelector from '$lib/components/DateSelector.svelte';
	import { type TrendRange, filterByRange, PERIOD_KEY_MAP } from '$lib/trend-range';
	import { fmt } from '$lib/format';
	import { COLORS, withAlpha } from '$lib/colors';
	import { darkLineOptions, simpleIntradayLineConfig } from '$lib/chart-options';
	import type { ChartConfiguration } from 'chart.js';

	let agg: SpO2Daily | null = $state(null);
	let intradayData: SpO2RawData | null = $state(null);
	let selectedDate = $state('');
	let trendRange: TrendRange = $state('3M');
	let loading = $state(true);
	let error: string | null = $state(null);

	async function fetchData() {
		agg = await api.getPulseOxDaily();
		const date = selectedDate;
		if (date) {
			const data = await api.getPulseOxRaw(date);
			if (selectedDate === date) {
				intradayData = data;
			}
		}
	}

	onMount(() => {
		return startRealtimePage({
			fetchData,
			setError: (message) => {
				error = message;
			},
			setLoading: (value) => {
				loading = value;
			}
		});
	});

	const onDateChange = createDateLoader<SpO2RawData>({
		setSelectedDate: (date) => {
			selectedDate = date;
		},
		clearData: () => {
			intradayData = null;
		},
		fetchByDate: (date) => api.getPulseOxRaw(date),
		setData: (data) => {
			intradayData = data;
		},
		setError: (message) => {
			error = message;
		}
	});

	let trendConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!agg) return null;
		const daily = filterByRange(agg.daily, trendRange);
		return {
			type: 'line',
			data: {
				labels: daily.map((d) => d.date),
				datasets: [
					{
						label: 'Avg SpO2',
						data: daily.map((d) => d.spo2.avg),
						borderColor: COLORS.spo2,
						borderWidth: 2,
						pointRadius: 2,
						tension: 0.3,
						spanGaps: false
					},
					{
						label: 'Q1 (25th)',
						data: daily.map((d) => d.spo2.q1),
						borderColor: withAlpha(COLORS.spo2, '40'),
						borderWidth: 1,
						borderDash: [4, 4],
						pointRadius: 0,
						tension: 0.3,
						spanGaps: false,
						fill: false
					},
					{
						label: 'Q3 (75th)',
						data: daily.map((d) => d.spo2.q3),
						borderColor: withAlpha(COLORS.spo2, '40'),
						borderWidth: 1,
						borderDash: [4, 4],
						pointRadius: 0,
						tension: 0.3,
						spanGaps: false,
						fill: '-1'
					},
					{
						label: 'Min SpO2',
						data: daily.map((d) => d.spo2.min),
						borderColor: COLORS.spo2Min,
						borderWidth: 1.5,
						borderDash: [4, 4],
						pointRadius: 1,
						tension: 0.3,
						spanGaps: false
					}
				]
			},
			options: darkLineOptions({ color: COLORS.spo2, yTitle: '%', beginAtZero: false, min: 85 })
		};
	});

	let intradayConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!intradayData || intradayData.spo2.length === 0) return null;
		return simpleIntradayLineConfig({
			label: 'SpO2',
			color: COLORS.spo2,
			yTitle: '%',
			labels: intradayData.spo2.map((d) => d.timestamp),
			values: intradayData.spo2.map((d) => d.value),
			beginAtZero: false,
			min: 85
		});
	});

	let stats = $derived.by(() => {
		const pw = agg?.period_windows?.[PERIOD_KEY_MAP[trendRange]];
		if (!pw) return null;
		const spo2 = pw;
		return {
			overallAvg: spo2.avg,
			lowestMin: spo2.lowest_min,
			lowDays: spo2.low_days,
			totalDays: spo2.total_days
		};
	});

	let intradayFootnote = $derived.by(() => `${intradayData?.spo2.length ?? 0} readings`);
</script>

<svelte:head><title>Pulse Ox - Garmin Stats</title></svelte:head>

<PageState error={agg ? null : error} {loading}>
	{#if agg}
		{#if error}
			<div class="mb-4 flex items-center justify-between gap-3 rounded-lg border border-[rgba(232,93,74,0.3)] bg-[rgba(232,93,74,0.08)] p-3">
				<p class="text-[#E85D4A]">Error: {error}</p>
				<button type="button" class="shrink-0 text-[#E85D4A] opacity-70 hover:opacity-100" onclick={() => (error = null)} aria-label="Dismiss error">✕</button>
			</div>
		{/if}
		<MetricPageHeader title="Pulse Ox (SpO2)" bind:trendRange />

		<MetricDefinition title="What is Pulse Ox / SpO2?">
			<p class="mb-2">
				Pulse oximetry (SpO2) measures the oxygen saturation of your blood. It represents the percentage
				of hemoglobin molecules carrying oxygen.
			</p>
			<p class="mb-2">
				<strong>Normal range:</strong> 95-100% for healthy individuals.
				Values <strong>below 90%</strong> are considered low and may be concerning.
			</p>
			<p>
				SpO2 can drop during sleep (especially at altitude), intense exercise, or with respiratory conditions.
				Garmin measures it periodically throughout the day and more frequently during sleep.
			</p>
		</MetricDefinition>

		<DateSelector days={agg.days} selected={selectedDate} onchange={onDateChange} />

		{#if stats}
			<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
				<StatCard title="Overall Avg" value={fmt(stats.overallAvg)} unit="%" color={COLORS.spo2} />
				<StatCard title="Lowest Reading" value={fmt(stats.lowestMin)} unit="%" color={COLORS.spo2Min} />
				<StatCard
					title="Days Below 90%"
					value={stats.lowDays ?? '-'}
					color={stats.lowDays ? COLORS.spo2Min : COLORS.heartRateResting}
					subtitle="of {stats.totalDays} days"
				/>
				<StatCard title="Days Tracked" value={stats.totalDays ?? '-'} color="#8a9baa" />
			</div>
		{/if}

		<ChartCard title="Daily Trend">
			{#if trendConfig}
				<LineChart config={trendConfig} height={300} />
			{/if}
		</ChartCard>

		{#if selectedDate && intradayConfig}
			<ChartCard title={`Intraday — ${selectedDate}`} footnote={intradayFootnote}>
				<LineChart config={intradayConfig} height={300} />
			</ChartCard>
		{:else if selectedDate}
			<div class="text-sm text-[#5e7282]">Loading intraday data...</div>
		{/if}
	{/if}
</PageState>
