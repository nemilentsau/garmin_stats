<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type DailyAggregates, type HrvData } from '$lib/api';
	import LineChart from '$lib/components/LineChart.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import MetricDefinition from '$lib/components/MetricDefinition.svelte';
	import DateSelector from '$lib/components/DateSelector.svelte';
	import { fmt } from '$lib/format';
	import { COLORS } from '$lib/colors';
	import type { ChartConfiguration } from 'chart.js';

	let agg: DailyAggregates | null = $state(null);
	let intradayData: HrvData | null = $state(null);
	let selectedDate = $state('');
	let loading = $state(true);
	let error: string | null = $state(null);

	onMount(async () => {
		try {
			agg = await api.getDailyAggregates();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : String(e);
		}
		loading = false;
	});

	async function onDateChange(date: string) {
		selectedDate = date;
		intradayData = null;
		if (date) {
			intradayData = await api.getHrv(date);
		}
	}

	let trendConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!agg) return null;
		return {
			type: 'line',
			data: {
				labels: agg.daily.map((d) => d.date),
				datasets: [
					{
						label: 'Nightly Avg',
						data: agg.daily.map((d) => d.hrv.nightly_avg),
						borderColor: COLORS.hrv,
						borderWidth: 2,
						pointRadius: 2,
						tension: 0.3,
						spanGaps: true
					},
					{
						label: 'Weekly Avg',
						data: agg.daily.map((d) => d.hrv.weekly_avg),
						borderColor: COLORS.hrvWeekly,
						borderWidth: 2,
						borderDash: [6, 3],
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
				plugins: { legend: { labels: { boxWidth: 12, font: { size: 11 } } } },
				scales: {
					x: { ticks: { maxRotation: 45, font: { size: 10 } } },
					y: { beginAtZero: false, title: { display: true, text: 'ms' } }
				}
			}
		};
	});

	let intradayConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!intradayData || intradayData.hrv_values.length === 0) return null;
		return {
			type: 'line',
			data: {
				labels: intradayData.hrv_values.map((d) => d.timestamp),
				datasets: [
					{
						label: 'HRV',
						data: intradayData.hrv_values.map((d) => d.value),
						borderColor: COLORS.hrv,
						borderWidth: 1.5,
						pointRadius: 1,
						tension: 0.2
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
					y: { beginAtZero: false, title: { display: true, text: 'ms' } }
				}
			}
		};
	});

	let stats = $derived.by(() => {
		if (!agg?.period) return null;
		const hrv = agg.period.hrv;
		return {
			avgNightly: hrv.avg_nightly,
			avgWeekly: hrv.avg_weekly,
			balancedPct: hrv.balanced_pct,
			totalDays: hrv.total_days
		};
	});
</script>

<svelte:head><title>HRV - Garmin Stats</title></svelte:head>

{#if error}
	<div class="bg-red-50 border border-red-200 rounded-lg p-4">
		<p class="text-red-700">Error: {error}</p>
	</div>
{:else if loading}
	<div class="flex items-center justify-center h-64">
		<div class="text-gray-500">Loading...</div>
	</div>
{:else if agg}
	<h1 class="text-xl font-bold text-gray-900 mb-4">Heart Rate Variability (HRV)</h1>

	<MetricDefinition title="What is HRV?">
		<p class="mb-2">
			Heart Rate Variability measures the variation in time between consecutive heartbeats. Higher HRV generally
			indicates better autonomic nervous system function and recovery capacity.
		</p>
		<p class="mb-2">
			<strong>Nightly average</strong> is measured during sleep for the most consistent reading.
			<strong>Weekly average</strong> smooths out daily fluctuations.
		</p>
		<p>
			Factors that lower HRV: poor sleep, alcohol, illness, overtraining, stress.
			Factors that raise HRV: good sleep, fitness, relaxation, recovery.
		</p>
	</MetricDefinition>

	<DateSelector days={agg.days} selected={selectedDate} onchange={onDateChange} />

	{#if stats}
		<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
			<StatCard title="Avg Nightly" value={fmt(stats?.avgNightly)} unit="ms" colorClass="text-purple-600" />
			<StatCard title="Avg Weekly" value={fmt(stats?.avgWeekly)} unit="ms" colorClass="text-purple-400" />
			<StatCard title="Balanced" value={stats?.balancedPct != null ? stats!.balancedPct + '%' : '-'} colorClass="text-green-600" subtitle="of {stats?.totalDays} days" />
			<StatCard title="Days Tracked" value={stats?.totalDays ?? '-'} colorClass="text-gray-700" />
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
				Intraday HRV — {selectedDate}
			</h2>
			<LineChart config={intradayConfig} height={300} />
			<p class="text-xs text-gray-400 mt-2">{intradayData?.hrv_values.length ?? 0} readings (5-min intervals during sleep)</p>
		</div>
	{:else if selectedDate}
		<div class="text-sm text-gray-500">Loading intraday data...</div>
	{/if}
{/if}
