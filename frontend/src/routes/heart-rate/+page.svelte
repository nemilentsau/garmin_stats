<script lang="ts">
	import { onMount } from 'svelte';
	import {
		api,
		type DailyAggregates,
		type DailyMetric,
		type WellnessData
	} from '$lib/api';
	import LineChart from '$lib/components/LineChart.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import MetricDefinition from '$lib/components/MetricDefinition.svelte';
	import DateSelector from '$lib/components/DateSelector.svelte';
	import type { ChartConfiguration } from 'chart.js';

	let agg: DailyAggregates | null = $state(null);
	let intradayData: WellnessData | null = $state(null);
	let selectedDate = $state('');
	let loading = $state(true);
	let error: string | null = $state(null);

	onMount(async () => {
		try {
			agg = await api.getDailyAggregates();
		} catch (e: any) {
			error = e.message;
		}
		loading = false;
	});

	async function onDateChange(date: string) {
		selectedDate = date;
		intradayData = null;
		if (date) {
			intradayData = await api.getWellness(date);
		}
	}

	function fmt(n: number | null | undefined): string {
		if (n == null) return '-';
		return Number.isInteger(n) ? n.toLocaleString() : n.toFixed(1);
	}

	let trendConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!agg) return null;
		return {
			type: 'line',
			data: {
				labels: agg.daily.map((d) => d.date),
				datasets: [
					{
						label: 'Avg HR',
						data: agg.daily.map((d) => d.heart_rate.avg),
						borderColor: '#dc2626',
						borderWidth: 2,
						pointRadius: 2,
						tension: 0.3,
						spanGaps: true
					},
					{
						label: 'Resting HR',
						data: agg.daily.map((d) => d.heart_rate.resting),
						borderColor: '#16a34a',
						borderWidth: 2,
						pointRadius: 2,
						tension: 0.3,
						spanGaps: true
					},
					{
						label: 'Min',
						data: agg.daily.map((d) => d.heart_rate.min),
						borderColor: '#dc262640',
						borderWidth: 1,
						borderDash: [4, 4],
						pointRadius: 0,
						tension: 0.3,
						spanGaps: true,
						fill: false
					},
					{
						label: 'Max',
						data: agg.daily.map((d) => d.heart_rate.max),
						borderColor: '#dc262640',
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
				plugins: { legend: { labels: { boxWidth: 12, font: { size: 11 } } } },
				scales: {
					x: { ticks: { maxRotation: 45, font: { size: 10 } } },
					y: { beginAtZero: false, title: { display: true, text: 'bpm' } }
				}
			}
		};
	});

	let intradayConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!intradayData || intradayData.heart_rate.length === 0) return null;
		return {
			type: 'line',
			data: {
				labels: intradayData.heart_rate.map((d) => d.timestamp),
				datasets: [
					{
						label: 'Heart Rate',
						data: intradayData.heart_rate.map((d) => d.value),
						borderColor: '#dc2626',
						borderWidth: 1.5,
						pointRadius: 0,
						tension: 0.2,
						fill: { target: 'origin', above: '#dc262610' }
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: { legend: { display: false } },
				scales: {
					x: {
						type: 'time',
						time: { unit: 'hour', displayFormats: { hour: 'HH:mm' } },
						ticks: { font: { size: 10 } }
					},
					y: { beginAtZero: false, title: { display: true, text: 'bpm' } }
				}
			}
		};
	});

	let stats = $derived.by(() => {
		if (!agg) return null;
		const d = agg.daily;
		const avgs = d.map((x) => x.heart_rate.avg).filter((x): x is number => x != null);
		const mins = d.map((x) => x.heart_rate.min).filter((x): x is number => x != null);
		const maxs = d.map((x) => x.heart_rate.max).filter((x): x is number => x != null);
		const resting = d.map((x) => x.heart_rate.resting).filter((x): x is number => x != null);
		return {
			overallAvg: avgs.length ? Math.round(avgs.reduce((a, b) => a + b, 0) / avgs.length) : null,
			lowestMin: mins.length ? Math.min(...mins) : null,
			highestMax: maxs.length ? Math.max(...maxs) : null,
			avgResting: resting.length
				? Math.round(resting.reduce((a, b) => a + b, 0) / resting.length)
				: null
		};
	});
</script>

<svelte:head><title>Heart Rate - Garmin Stats</title></svelte:head>

{#if error}
	<div class="bg-red-50 border border-red-200 rounded-lg p-4">
		<p class="text-red-700">Error: {error}</p>
	</div>
{:else if loading}
	<div class="flex items-center justify-center h-64">
		<div class="text-gray-500">Loading...</div>
	</div>
{:else if agg}
	<h1 class="text-xl font-bold text-gray-900 mb-4">Heart Rate</h1>

	<MetricDefinition title="What is Heart Rate?">
		<p class="mb-2">
			Heart rate measures how many times your heart beats per minute (bpm). <strong>Resting heart rate</strong> (RHR)
			is measured when you're calm and still — a lower RHR generally indicates better cardiovascular fitness.
		</p>
		<p class="mb-2">
			<strong>Normal resting range:</strong> 60-100 bpm for adults. Athletes may be 40-60 bpm.
		</p>
		<p>
			Trends in average and resting HR can indicate fitness improvements, overtraining,
			illness, or stress changes over time.
		</p>
	</MetricDefinition>

	<DateSelector days={agg.days} selected={selectedDate} onchange={onDateChange} />

	{#if stats}
		<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
			<StatCard title="Overall Avg" value={fmt(stats?.overallAvg)} unit="bpm" colorClass="text-red-600" />
			<StatCard title="Avg Resting" value={fmt(stats?.avgResting)} unit="bpm" colorClass="text-green-600" />
			<StatCard title="Lowest" value={fmt(stats?.lowestMin)} unit="bpm" colorClass="text-blue-600" />
			<StatCard title="Highest" value={fmt(stats?.highestMax)} unit="bpm" colorClass="text-orange-600" />
		</div>
	{/if}

	<div class="bg-white rounded-lg shadow p-5 mb-6">
		<h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">Daily Trend</h2>
		{#if trendConfig}
			<LineChart config={trendConfig} height={300} />
		{/if}
	</div>

	{#if selectedDate && intradayConfig}
		<div class="bg-white rounded-lg shadow p-5">
			<h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">
				Intraday — {selectedDate}
			</h2>
			<LineChart config={intradayConfig} height={300} />
			<p class="text-xs text-gray-400 mt-2">{intradayData?.heart_rate.length ?? 0} readings</p>
		</div>
	{:else if selectedDate}
		<div class="text-sm text-gray-500">Loading intraday data...</div>
	{/if}
{/if}
