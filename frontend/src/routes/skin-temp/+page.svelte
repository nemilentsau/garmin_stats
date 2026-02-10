<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type DailyAggregates } from '$lib/api';
	import { createDataUpdateListener } from '$lib/sse';
	import LineChart from '$lib/components/LineChart.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import MetricDefinition from '$lib/components/MetricDefinition.svelte';
	import { COLORS } from '$lib/colors';
	import type { ChartConfiguration } from 'chart.js';

	let agg: DailyAggregates | null = $state(null);
	let loading = $state(true);
	let error: string | null = $state(null);

	async function fetchData() {
		agg = await api.getDailyAggregates();
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

	function fmt(n: number | null | undefined): string {
		if (n == null) return '-';
		return n.toFixed(2);
	}

	let trendConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!agg) return null;
		return {
			type: 'line',
			data: {
				labels: agg.daily.map((d) => d.date),
				datasets: [
					{
						label: 'Deviation',
						data: agg.daily.map((d) => d.skin_temp.deviation),
						borderColor: COLORS.skinTemp,
						borderWidth: 2,
						pointRadius: 2,
						tension: 0.3,
						spanGaps: true
					},
					{
						label: '7-Day Smoothed',
						data: agg.daily.map((d) => d.skin_temp.deviation_7_day),
						borderColor: COLORS.skinTemp7Day,
						borderWidth: 2,
						borderDash: [6, 3],
						pointRadius: 0,
						tension: 0.3,
						spanGaps: true
					},
					{
						label: 'Baseline (0)',
						data: agg.daily.map(() => 0),
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
				plugins: { legend: { labels: { boxWidth: 12, font: { size: 11 } } } },
				scales: {
					x: { ticks: { maxRotation: 45, font: { size: 10 } } },
					y: { title: { display: true, text: '\u00B0C deviation' } }
				}
			}
		};
	});

	let stats = $derived.by(() => {
		if (!agg?.period) return null;
		const st = agg.period.skin_temp;
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
	<div class="bg-red-50 border border-red-200 rounded-lg p-4">
		<p class="text-red-700">Error: {error}</p>
	</div>
{:else if loading}
	<div class="flex items-center justify-center h-64">
		<div class="text-gray-500">Loading...</div>
	</div>
{:else if agg}
	<h1 class="text-xl font-bold text-gray-900 mb-4">Skin Temperature</h1>

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
			<StatCard title="Avg Deviation" value={stats?.avgDeviation ?? '-'} unit="&deg;C" colorClass="text-amber-600" />
			<StatCard title="Max Deviation" value={stats?.maxDeviation ?? '-'} unit="&deg;C" colorClass="text-red-600" />
			<StatCard title="Min Deviation" value={stats?.minDeviation ?? '-'} unit="&deg;C" colorClass="text-blue-600" />
			<StatCard title="Avg Nightly" value={stats?.avgNightly ?? '-'} unit="&deg;C" colorClass="text-gray-700" />
		</div>
	{/if}

	<div class="bg-white rounded-lg shadow p-5">
		<h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">
			Nightly Deviation Trend
		</h2>
		{#if trendConfig}
			<LineChart config={trendConfig} height={350} />
		{/if}
		<p class="text-xs text-gray-400 mt-2">
			{stats?.daysTracked ?? 0} nights tracked. Only 1 reading per night — no intraday view available.
		</p>
	</div>
{/if}
