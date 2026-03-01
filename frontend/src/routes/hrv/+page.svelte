<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type DailyAggregates, type HrvData } from '$lib/api';
	import { createDateLoader, startRealtimePage } from '$lib/realtime-page';
	import LineChart from '$lib/components/LineChart.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import MetricDefinition from '$lib/components/MetricDefinition.svelte';
	import DateSelector from '$lib/components/DateSelector.svelte';
	import { fmt } from '$lib/format';
	import { COLORS, withAlpha } from '$lib/colors';
	import type { ChartConfiguration } from 'chart.js';

	let agg: DailyAggregates | null = $state(null);
	let intradayData: HrvData | null = $state(null);
	let selectedDate = $state('');
	let loading = $state(true);
	let error: string | null = $state(null);

	async function fetchData() {
		agg = await api.getDailyAggregates();
		const date = selectedDate;
		if (date) {
			const data = await api.getHrv(date);
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

	const onDateChange = createDateLoader<HrvData>({
		setSelectedDate: (date) => {
			selectedDate = date;
		},
		clearData: () => {
			intradayData = null;
		},
		fetchByDate: (date) => api.getHrv(date),
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
				plugins: {
					legend: { labels: { boxWidth: 12, font: { size: 11 }, color: '#8a9baa' } },
					tooltip: { backgroundColor: '#1a2332', borderWidth: 1, borderColor: withAlpha(COLORS.hrv, '60'), padding: 10, cornerRadius: 4 }
				},
				scales: {
					x: {
						ticks: { maxRotation: 45, font: { size: 10 }, color: '#6b7d8e' },
						grid: { color: '#ffffff08' },
						border: { color: '#ffffff10' }
					},
					y: {
						beginAtZero: false,
						title: { display: true, text: 'ms', color: '#6b7d8e' },
						ticks: { color: '#6b7d8e' },
						grid: { color: '#ffffff06' },
						border: { color: '#ffffff10' }
					}
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
				plugins: {
					legend: { display: false },
					tooltip: { backgroundColor: '#1a2332', borderWidth: 1, borderColor: withAlpha(COLORS.hrv, '60'), padding: 10, cornerRadius: 4 }
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
						title: { display: true, text: 'ms', color: '#6b7d8e' },
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
	<div class="bg-[rgba(232,93,74,0.08)] border border-[rgba(232,93,74,0.3)] rounded-lg p-4">
		<p class="text-[#E85D4A]">Error: {error}</p>
	</div>
{:else if loading}
	<div class="flex items-center justify-center h-64">
		<div class="text-[#5e7282]">Loading...</div>
	</div>
{:else if agg}
	<h1 class="text-xl font-bold text-[#e8f0f5] mb-4">Heart Rate Variability (HRV)</h1>

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
			<StatCard title="Avg Nightly" value={fmt(stats?.avgNightly)} unit="ms" colorClass="text-[#9B6BCD]" />
			<StatCard title="Avg Weekly" value={fmt(stats?.avgWeekly)} unit="ms" colorClass="text-[#b794e0]" />
			<StatCard title="Balanced" value={stats?.balancedPct != null ? stats!.balancedPct + '%' : '-'} colorClass="text-[#4CAF82]" subtitle="of {stats?.totalDays} days" />
			<StatCard title="Days Tracked" value={stats?.totalDays ?? '-'} colorClass="text-[#8a9baa]" />
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
				Intraday HRV — {selectedDate}
			</h2>
			<LineChart config={intradayConfig} height={300} />
			<p class="text-xs text-[#4a5c6a] mt-2">{intradayData?.hrv_values.length ?? 0} readings (5-min intervals during sleep)</p>
		</div>
	{:else if selectedDate}
		<div class="text-sm text-[#5e7282]">Loading intraday data...</div>
	{/if}
{/if}
