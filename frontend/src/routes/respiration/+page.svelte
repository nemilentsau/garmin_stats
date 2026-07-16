<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type RespirationDaily, type RespirationRawData } from '$lib/api';
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

	let agg: RespirationDaily | null = $state(null);
	let intradayData: RespirationRawData | null = $state(null);
	let selectedDate = $state('');
	let trendRange: TrendRange = $state('3M');
	let loading = $state(true);
	let error: string | null = $state(null);

	async function fetchData() {
		agg = await api.getRespirationDaily();
		const date = selectedDate;
		if (date) {
			const data = await api.getRespirationRaw(date);
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

	const onDateChange = createDateLoader<RespirationRawData>({
		setSelectedDate: (date) => {
			selectedDate = date;
		},
		clearData: () => {
			intradayData = null;
		},
		fetchByDate: (date) => api.getRespirationRaw(date),
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
						label: 'Avg',
						data: daily.map((d) => d.respiration.avg),
						borderColor: COLORS.respiration,
						borderWidth: 2,
						pointRadius: 2,
						tension: 0.3,
						spanGaps: false
					},
					{
						label: 'Q1 (25th)',
						data: daily.map((d) => d.respiration.q1),
						borderColor: withAlpha(COLORS.respiration, '40'),
						borderWidth: 1,
						borderDash: [4, 4],
						pointRadius: 0,
						tension: 0.3,
						spanGaps: false,
						fill: false
					},
					{
						label: 'Q3 (75th)',
						data: daily.map((d) => d.respiration.q3),
						borderColor: withAlpha(COLORS.respiration, '40'),
						borderWidth: 1,
						borderDash: [4, 4],
						pointRadius: 0,
						tension: 0.3,
						spanGaps: false,
						fill: '-1'
					}
				]
			},
			options: darkLineOptions({ color: COLORS.respiration, yTitle: 'br/min', beginAtZero: false })
		};
	});

	let intradayConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!intradayData || intradayData.respiration.length === 0) return null;
		return simpleIntradayLineConfig({
			label: 'Respiration',
			color: COLORS.respiration,
			yTitle: 'br/min',
			labels: intradayData.respiration.map((d) => d.timestamp),
			values: intradayData.respiration.map((d) => d.value),
			beginAtZero: false
		});
	});

	let stats = $derived.by(() => {
		const pw = agg?.period_windows?.[PERIOD_KEY_MAP[trendRange]];
		if (!pw) return null;
		const resp = pw;
		return {
			overallAvg: resp.avg,
			typicalLow: resp.typical_low,
			typicalHigh: resp.typical_high
		};
	});

	let intradayFootnote = $derived.by(() => `${intradayData?.respiration.length ?? 0} readings`);
</script>

<svelte:head><title>Respiration - Garmin Stats</title></svelte:head>

<PageState {error} {loading}>
	{#if agg}
		<MetricPageHeader title="Respiration Rate" bind:trendRange />

		<MetricDefinition title="What is Respiration Rate?">
			<p class="mb-2">
				Respiration rate is the number of breaths you take per minute (br/min). It's measured continuously
				by your Garmin watch using the optical heart rate sensor.
			</p>
			<p class="mb-2">
				<strong>Normal range:</strong> 12-20 breaths/min for a healthy adult at rest.
			</p>
			<p>
				Elevated respiration can indicate stress, illness, fever, or intense exercise.
				Consistently elevated rates at rest may warrant medical attention.
			</p>
		</MetricDefinition>

		<DateSelector days={agg.days} selected={selectedDate} onchange={onDateChange} />

		{#if stats}
			<div class="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
				<StatCard title="Overall Avg" value={fmt(stats.overallAvg)} unit="br/min" color={COLORS.respiration} />
				<StatCard title="Typical Low" value={fmt(stats.typicalLow)} unit="br/min" color={COLORS.spo2} />
				<StatCard title="Typical High" value={fmt(stats.typicalHigh)} unit="br/min" color={COLORS.stress} />
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
