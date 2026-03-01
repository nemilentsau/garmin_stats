<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type DailyAggregates, type WellnessData } from '$lib/api';
	import { createDateLoader, startRealtimePage } from '$lib/realtime-page';
	import LineChart from '$lib/components/LineChart.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import MetricDefinition from '$lib/components/MetricDefinition.svelte';
	import DateSelector from '$lib/components/DateSelector.svelte';
	import { fmt } from '$lib/format';
	import { COLORS, withAlpha } from '$lib/colors';
	import type { ChartConfiguration } from 'chart.js';

	let agg: DailyAggregates | null = $state(null);
	let intradayData: WellnessData | null = $state(null);
	let selectedDate = $state('');
	let loading = $state(true);
	let error: string | null = $state(null);

	async function fetchData() {
		agg = await api.getDailyAggregates();
		const date = selectedDate;
		if (date) {
			const data = await api.getWellness(date);
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

	const onDateChange = createDateLoader<WellnessData>({
		setSelectedDate: (date) => {
			selectedDate = date;
		},
		clearData: () => {
			intradayData = null;
		},
		fetchByDate: (date) => api.getWellness(date),
		setData: (data) => {
			intradayData = data;
		},
		setError: (message) => {
			error = message;
		}
	});

	let trendConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!agg) return null;
		return {
			type: 'line',
			data: {
				labels: agg.daily.map((d) => d.date),
				datasets: [
					{
						label: 'Avg',
						data: agg.daily.map((d) => d.respiration.avg),
						borderColor: COLORS.respiration,
						borderWidth: 2,
						pointRadius: 2,
						tension: 0.3,
						spanGaps: true
					},
					{
						label: 'Q1 (25th)',
						data: agg.daily.map((d) => d.respiration.q1),
						borderColor: withAlpha(COLORS.respiration, '40'),
						borderWidth: 1,
						borderDash: [4, 4],
						pointRadius: 0,
						tension: 0.3,
						spanGaps: true,
						fill: false
					},
					{
						label: 'Q3 (75th)',
						data: agg.daily.map((d) => d.respiration.q3),
						borderColor: withAlpha(COLORS.respiration, '40'),
						borderWidth: 1,
						borderDash: [4, 4],
						pointRadius: 0,
						tension: 0.3,
						spanGaps: true,
						fill: '-1'
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				interaction: { mode: 'index' as const, intersect: false },
				plugins: {
					legend: { labels: { boxWidth: 12, font: { size: 11 }, color: '#8a9baa' } },
					tooltip: { backgroundColor: '#1a2332', borderWidth: 1, borderColor: withAlpha(COLORS.respiration, '60'), padding: 10, cornerRadius: 4 }
				},
				scales: {
					x: {
						ticks: { maxRotation: 45, font: { size: 10 }, color: '#6b7d8e' },
						grid: { color: '#ffffff08' },
						border: { color: '#ffffff10' }
					},
					y: {
						beginAtZero: false,
						title: { display: true, text: 'br/min', color: '#6b7d8e' },
						ticks: { color: '#6b7d8e' },
						grid: { color: '#ffffff06' },
						border: { color: '#ffffff10' }
					}
				}
			}
		};
	});

	let intradayConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!intradayData || intradayData.respiration.length === 0) return null;
		return {
			type: 'line',
			data: {
				labels: intradayData.respiration.map((d) => d.timestamp),
				datasets: [
					{
						label: 'Respiration',
						data: intradayData.respiration.map((d) => d.value),
						borderColor: COLORS.respiration,
						borderWidth: 1.5,
						pointRadius: 0,
						tension: 0.2,
						fill: { target: 'origin', above: withAlpha(COLORS.respiration, '10') }
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: false },
					tooltip: { backgroundColor: '#1a2332', borderWidth: 1, borderColor: withAlpha(COLORS.respiration, '60'), padding: 10, cornerRadius: 4 }
				},
				scales: {
					x: {
						type: 'time',
						time: { unit: 'hour', displayFormats: { hour: 'HH:mm' } },
						ticks: { font: { size: 10 }, color: '#6b7d8e' },
						grid: { color: '#ffffff08' },
						border: { color: '#ffffff10' }
					},
					y: {
						beginAtZero: false,
						title: { display: true, text: 'br/min', color: '#6b7d8e' },
						ticks: { color: '#6b7d8e' },
						grid: { color: '#ffffff06' },
						border: { color: '#ffffff10' }
					}
				}
			}
		};
	});

	let stats = $derived.by(() => {
		if (!agg?.period) return null;
		const resp = agg.period.respiration;
		return {
			overallAvg: resp.avg,
			typicalLow: resp.typical_low,
			typicalHigh: resp.typical_high
		};
	});
</script>

<svelte:head><title>Respiration - Garmin Stats</title></svelte:head>

{#if error}
	<div class="bg-[rgba(232,93,74,0.08)] border border-[rgba(232,93,74,0.3)] rounded-lg p-4">
		<p class="text-[#E85D4A]">Error: {error}</p>
	</div>
{:else if loading}
	<div class="flex items-center justify-center h-64">
		<div class="text-[#5e7282]">Loading...</div>
	</div>
{:else if agg}
	<h1 class="text-xl font-bold text-[#e8f0f5] mb-4">Respiration Rate</h1>

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
			<StatCard title="Overall Avg" value={fmt(stats?.overallAvg)} unit="br/min" colorClass="text-[#5BB5A6]" />
			<StatCard title="Typical Low" value={fmt(stats?.typicalLow)} unit="br/min" colorClass="text-[#4A90D9]" />
			<StatCard title="Typical High" value={fmt(stats?.typicalHigh)} unit="br/min" colorClass="text-[#D4944C]" />
		</div>
	{/if}

	<div class="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-5 mb-6">
		<h2 class="text-sm font-semibold text-[#8a9baa] uppercase tracking-wide mb-3">Daily Trend</h2>
		{#if trendConfig}
			<LineChart config={trendConfig} height={300} />
		{/if}
	</div>

	{#if selectedDate && intradayConfig}
		<div class="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-5">
			<h2 class="text-sm font-semibold text-[#8a9baa] uppercase tracking-wide mb-3">
				Intraday — {selectedDate}
			</h2>
			<LineChart config={intradayConfig} height={300} />
			<p class="text-xs text-[#4a5c6a] mt-2">{intradayData?.respiration.length ?? 0} readings</p>
		</div>
	{:else if selectedDate}
		<div class="text-sm text-[#5e7282]">Loading intraday data...</div>
	{/if}
{/if}
