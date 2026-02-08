<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type DailyAggregates, type DailyMetric } from '$lib/api';
	import LineChart from '$lib/components/LineChart.svelte';
	import { fmt } from '$lib/format';
	import { COLORS, withAlpha } from '$lib/colors';
	import type { ChartConfiguration } from 'chart.js';

	let data: DailyAggregates | null = $state(null);
	let error: string | null = $state(null);

	onMount(async () => {
		try {
			data = await api.getDailyAggregates();
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : String(e);
		}
	});

	function makeLineConfig(
		daily: DailyMetric[],
		getValue: (d: DailyMetric) => number | null,
		label: string,
		color: string,
		getQ1?: (d: DailyMetric) => number | null,
		getQ3?: (d: DailyMetric) => number | null
	): ChartConfiguration<'line'> {
		const labels = daily.map((d) => d.date);
		const datasets: ChartConfiguration<'line'>['data']['datasets'] = [
			{
				label,
				data: daily.map(getValue),
				borderColor: color,
				backgroundColor: withAlpha(color, '20'),
				borderWidth: 2,
				pointRadius: 2,
				tension: 0.3,
				spanGaps: true
			}
		];
		if (getQ1 && getQ3) {
			datasets.push({
				label: 'Q1 (25th)',
				data: daily.map(getQ1),
				borderColor: withAlpha(color, '40'),
				borderWidth: 1,
				borderDash: [4, 4],
				pointRadius: 0,
				tension: 0.3,
				spanGaps: true,
				fill: false
			});
			datasets.push({
				label: 'Q3 (75th)',
				data: daily.map(getQ3),
				borderColor: withAlpha(color, '40'),
				borderWidth: 1,
				borderDash: [4, 4],
				pointRadius: 0,
				tension: 0.3,
				spanGaps: true,
				fill: '-1'
			});
		}
		return {
			type: 'line',
			data: { labels, datasets },
			options: {
				responsive: true,
				maintainAspectRatio: false,
				interaction: { mode: 'index', intersect: false },
				plugins: { legend: { display: datasets.length > 1, labels: { boxWidth: 12, font: { size: 11 } } } },
				scales: {
					x: { ticks: { maxRotation: 45, font: { size: 10 } } },
					y: { beginAtZero: false, ticks: { font: { size: 10 } } }
				}
			}
		};
	}

	let hrConfig = $derived.by(() => {
		if (!data) return null;
		return makeLineConfig(data.daily, (d) => d.heart_rate.avg, 'Avg HR', COLORS.heartRate, (d) => d.heart_rate.q1, (d) => d.heart_rate.q3);
	});
	let stressConfig = $derived.by(() => {
		if (!data) return null;
		return makeLineConfig(data.daily, (d) => d.stress.avg, 'Avg Stress', COLORS.stress, (d) => d.stress.q1, (d) => d.stress.q3);
	});
	let bbConfig = $derived.by(() => {
		if (!data) return null;
		return makeLineConfig(data.daily, (d) => d.body_battery.avg, 'Avg Body Battery', COLORS.bodyBattery, (d) => d.body_battery.q1, (d) => d.body_battery.q3);
	});
	let spo2Config = $derived.by(() => {
		if (!data) return null;
		return makeLineConfig(data.daily, (d) => d.spo2.avg, 'Avg SpO2', COLORS.spo2, (d) => d.spo2.q1, (d) => d.spo2.q3);
	});
	let respConfig = $derived.by(() => {
		if (!data) return null;
		return makeLineConfig(data.daily, (d) => d.respiration.avg, 'Avg Respiration', COLORS.respiration, (d) => d.respiration.q1, (d) => d.respiration.q3);
	});
	let hrvConfig = $derived.by(() => {
		if (!data) return null;
		const labels = data.daily.map((d) => d.date);
		return {
			type: 'line' as const,
			data: {
				labels,
				datasets: [
					{
						label: 'Nightly Avg',
						data: data.daily.map((d) => d.hrv.nightly_avg),
						borderColor: COLORS.hrv,
						borderWidth: 2,
						pointRadius: 2,
						tension: 0.3,
						spanGaps: true
					},
					{
						label: 'Weekly Avg',
						data: data.daily.map((d) => d.hrv.weekly_avg),
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
					y: { beginAtZero: false, ticks: { font: { size: 10 } } }
				}
			}
		};
	});
	let sleepConfig = $derived.by(() => {
		if (!data) return null;
		return makeLineConfig(data.daily, (d) => d.sleep.score, 'Sleep Score', COLORS.sleep);
	});
	let skinTempConfig = $derived.by(() => {
		if (!data) return null;
		const labels = data.daily.map((d) => d.date);
		return {
			type: 'line' as const,
			data: {
				labels,
				datasets: [
					{
						label: 'Deviation',
						data: data.daily.map((d) => d.skin_temp.deviation),
						borderColor: COLORS.skinTemp,
						borderWidth: 2,
						pointRadius: 2,
						tension: 0.3,
						spanGaps: true
					},
					{
						label: '7-Day Avg',
						data: data.daily.map((d) => d.skin_temp.deviation_7_day),
						borderColor: COLORS.skinTemp7Day,
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
					y: { beginAtZero: false, ticks: { font: { size: 10 } } }
				}
			}
		};
	});

	function latestValid<T>(daily: DailyMetric[], getter: (d: DailyMetric) => T | null): T | null {
		for (let i = daily.length - 1; i >= 0; i--) {
			const v = getter(daily[i]);
			if (v != null) return v;
		}
		return null;
	}
</script>

{#if error}
	<div class="bg-red-50 border border-red-200 rounded-lg p-4">
		<p class="text-red-700">Error: {error}</p>
		<p class="text-sm text-red-600 mt-2">Make sure the backend is running at localhost:8000</p>
	</div>
{:else if !data}
	<div class="flex items-center justify-center h-64">
		<div class="text-gray-500">Loading data...</div>
	</div>
{:else}
	<div class="mb-4 text-sm text-gray-500">
		{data.days.length} days &middot; {data.days[0]} to {data.days[data.days.length - 1]}
	</div>

	<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
		<!-- Heart Rate Panel -->
		<div class="bg-white rounded-lg shadow p-5">
			<div class="flex items-baseline justify-between mb-3">
				<h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide">Heart Rate</h2>
				<div class="text-right">
					<span class="text-xl font-bold text-red-600">{fmt(latestValid(data.daily, (d) => d.heart_rate.avg))}</span>
					<span class="text-xs text-gray-500">bpm avg</span>
					{#if latestValid(data.daily, (d) => d.heart_rate.resting)}
						<span class="ml-2 text-xs text-gray-400">resting {fmt(latestValid(data.daily, (d) => d.heart_rate.resting))}</span>
					{/if}
				</div>
			</div>
			{#if hrConfig}
				<LineChart config={hrConfig} height={220} />
			{/if}
		</div>

		<!-- Stress Panel -->
		<div class="bg-white rounded-lg shadow p-5">
			<div class="flex items-baseline justify-between mb-3">
				<h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide">Stress</h2>
				<div class="text-right">
					<span class="text-xl font-bold text-orange-600">{fmt(latestValid(data.daily, (d) => d.stress.avg))}</span>
					<span class="text-xs text-gray-500">avg</span>
				</div>
			</div>
			{#if stressConfig}
				<LineChart config={stressConfig} height={220} />
			{/if}
		</div>

		<!-- Body Battery Panel -->
		<div class="bg-white rounded-lg shadow p-5">
			<div class="flex items-baseline justify-between mb-3">
				<h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide">Body Battery</h2>
				<div class="text-right">
					<span class="text-xl font-bold text-emerald-600">{fmt(latestValid(data.daily, (d) => d.body_battery.avg))}</span>
					<span class="text-xs text-gray-500">avg</span>
				</div>
			</div>
			{#if bbConfig}
				<LineChart config={bbConfig} height={220} />
			{/if}
		</div>

		<!-- SpO2 Panel -->
		<div class="bg-white rounded-lg shadow p-5">
			<div class="flex items-baseline justify-between mb-3">
				<h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide">SpO2</h2>
				<div class="text-right">
					<span class="text-xl font-bold text-blue-600">{fmt(latestValid(data.daily, (d) => d.spo2.avg))}</span>
					<span class="text-xs text-gray-500">%</span>
				</div>
			</div>
			{#if spo2Config}
				<LineChart config={spo2Config} height={220} />
			{/if}
		</div>

		<!-- Respiration Panel -->
		<div class="bg-white rounded-lg shadow p-5">
			<div class="flex items-baseline justify-between mb-3">
				<h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide">Respiration</h2>
				<div class="text-right">
					<span class="text-xl font-bold text-teal-600">{fmt(latestValid(data.daily, (d) => d.respiration.avg))}</span>
					<span class="text-xs text-gray-500">br/min</span>
				</div>
			</div>
			{#if respConfig}
				<LineChart config={respConfig} height={220} />
			{/if}
		</div>

		<!-- HRV Panel -->
		<div class="bg-white rounded-lg shadow p-5">
			<div class="flex items-baseline justify-between mb-3">
				<h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide">HRV</h2>
				<div class="text-right">
					<span class="text-xl font-bold text-purple-600">{fmt(latestValid(data.daily, (d) => d.hrv.nightly_avg))}</span>
					<span class="text-xs text-gray-500">ms nightly</span>
				</div>
			</div>
			{#if hrvConfig}
				<LineChart config={hrvConfig} height={220} />
			{/if}
		</div>

		<!-- Sleep Score Panel -->
		<div class="bg-white rounded-lg shadow p-5">
			<div class="flex items-baseline justify-between mb-3">
				<h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide">Sleep Score</h2>
				<div class="text-right">
					<span class="text-xl font-bold text-indigo-600">{fmt(latestValid(data.daily, (d) => d.sleep.score))}</span>
					<span class="text-xs text-gray-500">latest</span>
				</div>
			</div>
			{#if sleepConfig}
				<LineChart config={sleepConfig} height={220} />
			{/if}
		</div>

		<!-- Skin Temp Panel -->
		<div class="bg-white rounded-lg shadow p-5 lg:col-span-2">
			<div class="flex items-baseline justify-between mb-3">
				<h2 class="text-sm font-semibold text-gray-700 uppercase tracking-wide">Skin Temperature</h2>
				<div class="text-right">
					<span class="text-xl font-bold text-amber-600">{fmt(latestValid(data.daily, (d) => d.skin_temp.deviation))}</span>
					<span class="text-xs text-gray-500">&deg;C deviation</span>
				</div>
			</div>
			{#if skinTempConfig}
				<LineChart config={skinTempConfig} height={200} />
			{/if}
		</div>
	</div>
{/if}
