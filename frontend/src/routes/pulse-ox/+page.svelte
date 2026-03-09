<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type DailyAggregates, type WellnessData } from '$lib/api';
	import { createDateLoader, startRealtimePage } from '$lib/realtime-page';
	import LineChart from '$lib/components/LineChart.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import MetricDefinition from '$lib/components/MetricDefinition.svelte';
	import DateSelector from '$lib/components/DateSelector.svelte';
	import TrendRangePicker from '$lib/components/TrendRangePicker.svelte';
	import { type TrendRange, filterByRange, PERIOD_KEY_MAP } from '$lib/trend-range';
	import { fmt } from '$lib/format';
	import { COLORS, withAlpha } from '$lib/colors';
	import { chartTooltip, DARK_GRID, DARK_GRID_Y, DARK_BORDER, DARK_TICK } from '$lib/chart-setup';
	import type { ChartConfiguration } from 'chart.js';

	let agg: DailyAggregates | null = $state(null);
	let intradayData: WellnessData | null = $state(null);
	let selectedDate = $state('');
	let trendRange: TrendRange = $state('3M');
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
						spanGaps: true
					},
					{
						label: 'Q1 (25th)',
						data: daily.map((d) => d.spo2.q1),
						borderColor: withAlpha(COLORS.spo2, '40'),
						borderWidth: 1,
						borderDash: [4, 4],
						pointRadius: 0,
						tension: 0.3,
						spanGaps: true,
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
						spanGaps: true,
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
					tooltip: chartTooltip(withAlpha(COLORS.spo2, '60'))
				},
				scales: {
					x: {
						ticks: { maxRotation: 45, font: { size: 10 }, ...DARK_TICK },
						grid: DARK_GRID,
						border: DARK_BORDER
					},
					y: {
						beginAtZero: false,
						title: { display: true, text: '%', ...DARK_TICK },
						min: 85,
						ticks: DARK_TICK,
						grid: DARK_GRID_Y,
						border: DARK_BORDER
					}
				}
			}
		};
	});

	let intradayConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!intradayData || intradayData.spo2.length === 0) return null;
		return {
			type: 'line',
			data: {
				labels: intradayData.spo2.map((d) => d.timestamp),
				datasets: [
					{
						label: 'SpO2',
						data: intradayData.spo2.map((d) => d.value),
						borderColor: COLORS.spo2,
						borderWidth: 1.5,
						pointRadius: 0,
						tension: 0.2,
						fill: { target: 'origin', above: withAlpha(COLORS.spo2, '10') }
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: false },
					tooltip: chartTooltip(withAlpha(COLORS.spo2, '60'))
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
						beginAtZero: false,
						title: { display: true, text: '%', ...DARK_TICK },
						min: 85,
						ticks: DARK_TICK,
						grid: DARK_GRID_Y,
						border: DARK_BORDER
					}
				}
			}
		};
	});

	let stats = $derived.by(() => {
		const pw = agg?.period_windows?.[PERIOD_KEY_MAP[trendRange]];
		if (!pw) return null;
		const spo2 = pw.spo2;
		return {
			overallAvg: spo2.avg,
			lowestMin: spo2.lowest_min,
			lowDays: spo2.low_days,
			totalDays: spo2.total_days
		};
	});
</script>

<svelte:head><title>Pulse Ox - Garmin Stats</title></svelte:head>

{#if error}
	<div class="bg-[rgba(232,93,74,0.08)] border border-[rgba(232,93,74,0.3)] rounded-lg p-4">
		<p class="text-[#E85D4A]">Error: {error}</p>
	</div>
{:else if loading}
	<div class="flex items-center justify-center h-64">
		<div class="text-[#5e7282]">Loading...</div>
	</div>
{:else if agg}
	<div class="flex items-center justify-between mb-4">
		<h1 class="text-xl font-bold text-[#e8f0f5]">Pulse Ox (SpO2)</h1>
		<TrendRangePicker bind:value={trendRange} />
	</div>

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
			<StatCard title="Overall Avg" value={fmt(stats?.overallAvg)} unit="%" colorClass="text-[#4A90D9]" />
			<StatCard title="Lowest Reading" value={fmt(stats?.lowestMin)} unit="%" colorClass="text-[#E85D4A]" />
			<StatCard
				title="Days Below 90%"
				value={stats?.lowDays ?? '-'}
				colorClass={stats?.lowDays ? 'text-[#E85D4A]' : 'text-[#4CAF82]'}
				subtitle="of {stats?.totalDays} days"
			/>
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
				Intraday — {selectedDate}
			</h2>
			<LineChart config={intradayConfig} height={300} />
			<p class="text-xs text-[#4a5c6a] mt-2">{intradayData?.spo2.length ?? 0} readings</p>
		</div>
	{:else if selectedDate}
		<div class="text-sm text-[#5e7282]">Loading intraday data...</div>
	{/if}
{/if}
