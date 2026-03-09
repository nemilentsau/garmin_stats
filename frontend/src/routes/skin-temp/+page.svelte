<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type DailyAggregates } from '$lib/api';
	import { startRealtimePage } from '$lib/realtime-page';
	import LineChart from '$lib/components/LineChart.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import MetricDefinition from '$lib/components/MetricDefinition.svelte';
	import TrendRangePicker from '$lib/components/TrendRangePicker.svelte';
	import { type TrendRange, filterByRange, PERIOD_KEY_MAP } from '$lib/trend-range';
	import { COLORS, withAlpha } from '$lib/colors';
	import { chartTooltip, DARK_GRID, DARK_GRID_Y, DARK_BORDER, DARK_TICK } from '$lib/chart-setup';
	import type { ChartConfiguration } from 'chart.js';

	let agg: DailyAggregates | null = $state(null);
	let loading = $state(true);
	let error: string | null = $state(null);
	let trendRange: TrendRange = $state('3M');

	async function fetchData() {
		agg = await api.getDailyAggregates();
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

	function fmt(n: number | null | undefined): string {
		if (n == null) return '-';
		return n.toFixed(2);
	}

	let trendConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!agg) return null;
		const daily = filterByRange(agg.daily, trendRange);
		return {
			type: 'line',
			data: {
				labels: daily.map((d) => d.date),
				datasets: [
					{
						label: 'Deviation',
						data: daily.map((d) => d.skin_temp.deviation),
						borderColor: COLORS.skinTemp,
						borderWidth: 2,
						pointRadius: 2,
						tension: 0.3,
						spanGaps: true
					},
					{
						label: '7-Day Smoothed',
						data: daily.map((d) => d.skin_temp.deviation_7_day),
						borderColor: COLORS.skinTemp7Day,
						borderWidth: 2,
						borderDash: [6, 3],
						pointRadius: 0,
						tension: 0.3,
						spanGaps: true
					},
					{
						label: 'Baseline (0)',
						data: daily.map(() => 0),
						borderColor: COLORS.baseline,
						borderWidth: 1,
						borderDash: [2, 2],
						pointRadius: 0
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				interaction: { mode: 'index' as const, intersect: false },
				plugins: {
					legend: { labels: { boxWidth: 12, font: { size: 11 }, color: '#8a9baa' } },
					tooltip: chartTooltip(withAlpha(COLORS.skinTemp, '60'))
				},
				scales: {
					x: {
						ticks: { maxRotation: 45, font: { size: 10 }, ...DARK_TICK },
						grid: DARK_GRID,
						border: DARK_BORDER
					},
					y: {
						title: { display: true, text: '\u00B0C deviation', ...DARK_TICK },
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
		const st = pw.skin_temp;
		return {
			avgDeviation: st.avg_deviation?.toFixed(2) ?? null,
			maxDeviation: st.max_deviation?.toFixed(2) ?? null,
			minDeviation: st.min_deviation?.toFixed(2) ?? null,
			avgNightly: st.avg_nightly?.toFixed(1) ?? null,
			daysTracked: st.days_tracked
		};
	});
</script>

<svelte:head><title>Skin Temp - Garmin Stats</title></svelte:head>

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
		<h1 class="text-xl font-bold text-[#e8f0f5]">Skin Temperature</h1>
		<TrendRangePicker bind:value={trendRange} />
	</div>

	<MetricDefinition title="What is Skin Temperature?">
		<p class="mb-2">
			Garmin measures wrist skin temperature overnight and reports it as a <strong>deviation</strong> from
			your personal baseline. Values are shown in degrees Celsius above or below your norm.
		</p>
		<p class="mb-2">
			<strong>Positive deviation</strong> may indicate illness, fever, or environmental heat.
			<strong>Negative deviation</strong> may indicate cold exposure or certain recovery states.
		</p>
		<p>
			The 7-day smoothed average helps identify sustained shifts versus normal daily fluctuation.
			Consistent positive shifts of +0.5&deg;C or more may warrant attention.
		</p>
	</MetricDefinition>

	{#if stats}
		<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
			<StatCard title="Avg Deviation" value={stats?.avgDeviation ?? '-'} unit="&deg;C" colorClass="text-[#C9933A]" />
			<StatCard title="Max Deviation" value={stats?.maxDeviation ?? '-'} unit="&deg;C" colorClass="text-[#E85D4A]" />
			<StatCard title="Min Deviation" value={stats?.minDeviation ?? '-'} unit="&deg;C" colorClass="text-[#4A90D9]" />
			<StatCard title="Avg Nightly" value={stats?.avgNightly ?? '-'} unit="&deg;C" colorClass="text-[#8a9baa]" />
		</div>
	{/if}

	<div class="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-5">
		<h2 class="text-sm font-semibold text-[#8a9baa] uppercase tracking-wide mb-3">
			Nightly Deviation Trend
		</h2>
		{#if trendConfig}
			<LineChart config={trendConfig} height={350} />
		{/if}
		<p class="text-xs text-[#4a5c6a] mt-2">
			{stats?.daysTracked ?? 0} nights tracked. Only 1 reading per night — no intraday view available.
		</p>
	</div>
{/if}
