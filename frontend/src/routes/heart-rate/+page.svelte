<script lang="ts">
	import { onMount } from 'svelte';
	import {
		api,
		type DailyAggregates,
		type DailyMetric,
		type WellnessData
	} from '$lib/api';
	import { createDataUpdateListener } from '$lib/sse';
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
		if (selectedDate) {
			intradayData = await api.getWellness(selectedDate);
		}
	}

	onMount(() => {
		fetchData()
			.catch((e: unknown) => {
				error = e instanceof Error ? e.message : String(e);
			})
			.finally(() => {
				loading = false;
			});

		return createDataUpdateListener(() => {
			fetchData();
		});
	});

	async function onDateChange(date: string) {
		selectedDate = date;
		intradayData = null;
		if (date) {
			intradayData = await api.getWellness(date);
		}
	}

	const darkScales = {
		x: {
			ticks: { maxRotation: 45, font: { size: 10 }, color: '#6b7d8e' },
			grid: { color: '#ffffff08' },
			border: { color: '#ffffff10' }
		},
		y: {
			beginAtZero: false,
			title: { display: true, text: 'bpm', color: '#6b7d8e' },
			ticks: { color: '#6b7d8e' },
			grid: { color: '#ffffff06' },
			border: { color: '#ffffff10' }
		}
	} as const;

	const darkPlugins = {
		legend: { labels: { boxWidth: 12, font: { size: 11 }, color: '#8a9baa' } },
		tooltip: {
			backgroundColor: '#1a2332',
			borderWidth: 1,
			borderColor: withAlpha(COLORS.heartRate, '60'),
			padding: 10,
			cornerRadius: 4
		}
	} as const;

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
						borderColor: COLORS.heartRate,
						borderWidth: 2,
						pointRadius: 2,
						tension: 0.3,
						spanGaps: true
					},
					{
						label: 'Resting HR',
						data: agg.daily.map((d) => d.heart_rate.resting),
						borderColor: COLORS.heartRateResting,
						borderWidth: 2,
						pointRadius: 2,
						tension: 0.3,
						spanGaps: true
					},
					{
						label: 'Q1 (25th)',
						data: agg.daily.map((d) => d.heart_rate.q1),
						borderColor: withAlpha(COLORS.heartRate, '80'),
						borderWidth: 1,
						borderDash: [4, 4],
						pointRadius: 0,
						tension: 0.3,
						spanGaps: true,
						fill: false
					},
					{
						label: 'Q3 (75th)',
						data: agg.daily.map((d) => d.heart_rate.q3),
						borderColor: withAlpha(COLORS.heartRate, '80'),
						borderWidth: 1,
						borderDash: [4, 4],
						pointRadius: 0,
						tension: 0.3,
						spanGaps: true,
						fill: '-1',
						backgroundColor: withAlpha(COLORS.heartRate, '12')
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				interaction: { mode: 'index' as const, intersect: false },
				plugins: darkPlugins,
				scales: darkScales
			}
		};
	});

	// Day-level stats derived from daily aggregates
	let dayStats = $derived.by(() => {
		if (!agg || !selectedDate) return null;
		const day = agg.daily.find((d) => d.date === selectedDate);
		if (!day) return null;
		return day.heart_rate;
	});

	let intradayConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!intradayData || intradayData.heart_rate.length === 0) return null;
		const datasets: ChartConfiguration<'line'>['data']['datasets'] = [
			{
				label: 'Heart Rate',
				data: intradayData.heart_rate.map((d) => d.value),
				borderColor: COLORS.heartRate,
				borderWidth: 1.5,
				pointRadius: 0,
				tension: 0.2,
				fill: { target: 'origin', above: withAlpha(COLORS.heartRate, '18') }
			}
		];
		// Add resting HR reference line if available
		if (dayStats?.resting != null) {
			const restingVal = dayStats.resting;
			datasets.push({
				label: 'Resting HR',
				data: intradayData.heart_rate.map(() => restingVal),
				borderColor: COLORS.heartRateResting,
				borderWidth: 1,
				borderDash: [6, 4],
				pointRadius: 0,
				tension: 0,
				fill: false
			});
		}
		return {
			type: 'line',
			data: {
				labels: intradayData.heart_rate.map((d) => d.timestamp),
				datasets
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: datasets.length > 1, labels: { boxWidth: 12, font: { size: 11 }, color: '#8a9baa' } },
					tooltip: { backgroundColor: '#1a2332', borderWidth: 1, borderColor: withAlpha(COLORS.heartRate, '60'), padding: 10, cornerRadius: 4 }
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
						title: { display: true, text: 'bpm', color: '#6b7d8e' },
						ticks: { color: '#6b7d8e' },
						grid: { color: '#ffffff06' },
						border: { color: '#ffffff10' }
					}
				}
			}
		};
	});

	// Zone colors (presentation only — zone data comes from backend)
	const ZONE_COLORS: Record<string, string> = {
		Rest: '#4A6FA5',
		Light: '#4CAF82',
		Moderate: '#D4944C',
		Vigorous: '#E85D4A'
	};

	let zoneBreakdown = $derived.by(() => {
		if (!dayStats || dayStats.zones.length === 0) return null;
		return dayStats.zones.map((z) => ({
			label: z.label,
			color: ZONE_COLORS[z.label] ?? '#6b7d8e',
			pct: z.pct
		}));
	});

	let stats = $derived.by(() => {
		if (!agg?.period) return null;
		const hr = agg.period.heart_rate;
		return {
			overallAvg: hr.avg,
			typicalLow: hr.typical_low,
			typicalHigh: hr.typical_high,
			avgResting: hr.avg_resting
		};
	});
</script>

<svelte:head><title>Heart Rate - Garmin Stats</title></svelte:head>

{#if error}
	<div class="bg-[rgba(232,93,74,0.08)] border border-[rgba(232,93,74,0.3)] rounded-lg p-4">
		<p class="text-[#E85D4A]">Error: {error}</p>
	</div>
{:else if loading}
	<div class="flex items-center justify-center h-64">
		<div class="text-[#5e7282]">Loading...</div>
	</div>
{:else if agg}
	<h1 class="text-xl font-bold text-[#e8f0f5] mb-4">Heart Rate</h1>

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
			<StatCard title="Overall Avg" value={fmt(stats?.overallAvg)} unit="bpm" colorClass="text-[#E85D4A]" />
			<StatCard title="Avg Resting" value={fmt(stats?.avgResting)} unit="bpm" colorClass="text-[#4CAF82]" />
			<StatCard title="Typical Low" value={fmt(stats?.typicalLow)} unit="bpm" colorClass="text-[#4A90D9]" />
			<StatCard title="Typical High" value={fmt(stats?.typicalHigh)} unit="bpm" colorClass="text-[#D4944C]" />
		</div>
	{/if}

	{#if dayStats}
		<div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
			<StatCard title="Min" value={fmt(dayStats.min)} unit="bpm" colorClass="text-[#4A90D9]" />
			<StatCard title="Max" value={fmt(dayStats.max)} unit="bpm" colorClass="text-[#D4944C]" />
			<StatCard title="Avg" value={fmt(dayStats.avg)} unit="bpm" colorClass="text-[#E85D4A]" />
			<StatCard title="Resting" value={fmt(dayStats.resting)} unit="bpm" colorClass="text-[#4CAF82]" />
			<StatCard title="Median" value={fmt(dayStats.median)} unit="bpm" colorClass="text-[#8a9baa]" />
		</div>
	{/if}

	<div class="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-5 mb-6">
		<h2 class="text-sm font-semibold text-[#8a9baa] uppercase tracking-wide mb-3">Daily Trend</h2>
		{#if trendConfig}
			<LineChart config={trendConfig} height={300} />
		{/if}
	</div>

	{#if selectedDate && intradayConfig}
		<div class="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-5 mb-6">
			<h2 class="text-sm font-semibold text-[#8a9baa] uppercase tracking-wide mb-3">
				Intraday — {selectedDate}
			</h2>
			<LineChart config={intradayConfig} height={300} />
			<p class="text-xs text-[#4a5c6a] mt-2">{intradayData?.heart_rate.length ?? 0} readings</p>
		</div>

		{#if zoneBreakdown}
			<div class="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-5">
				<h2 class="text-sm font-semibold text-[#8a9baa] uppercase tracking-wide mb-3">HR Zones</h2>
				<div class="flex h-6 rounded overflow-hidden">
					{#each zoneBreakdown as zone}
						<div
							class="flex items-center justify-center text-[10px] font-medium text-white/90"
							style="width: {zone.pct}%; background-color: {zone.color};"
							title="{zone.label}: {zone.pct}%"
						>
							{#if zone.pct >= 8}{zone.pct}%{/if}
						</div>
					{/each}
				</div>
				<div class="flex gap-4 mt-2">
					{#each zoneBreakdown as zone}
						<div class="flex items-center gap-1.5 text-xs text-[#8a9baa]">
							<span class="inline-block w-2.5 h-2.5 rounded-sm" style="background-color: {zone.color};"></span>
							{zone.label} {zone.pct}%
						</div>
					{/each}
				</div>
			</div>
		{/if}
	{:else if selectedDate}
		<div class="text-sm text-[#5e7282]">Loading intraday data...</div>
	{/if}
{/if}
