<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type DailyAggregates, type HrvInsights } from '$lib/api';
	import { startRealtimePage } from '$lib/realtime-page';
	import LineChart from '$lib/components/LineChart.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import MetricDefinition from '$lib/components/MetricDefinition.svelte';
	import DateSelector from '$lib/components/DateSelector.svelte';
	import { fmt } from '$lib/format';
	import { COLORS, withAlpha } from '$lib/colors';
	import type { ChartConfiguration } from 'chart.js';

	let agg: DailyAggregates | null = $state(null);
	let insights: HrvInsights | null = $state(null);
	let selectedDate = $state('');
	let loading = $state(true);
	let error: string | null = $state(null);
	let dateRequestId = 0;

	async function fetchData() {
		const date = selectedDate || undefined;
		const [nextAgg, nextInsights] = await Promise.all([
			api.getDailyAggregates(),
			api.getHrvInsights(date)
		]);
		if ((selectedDate || undefined) !== date) {
			return;
		}
		agg = nextAgg;
		insights = nextInsights;
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

	async function onDateChange(date: string) {
		selectedDate = date;
		insights = null;
		const requestId = ++dateRequestId;
		try {
			const nextInsights = await api.getHrvInsights(date || undefined);
			if (requestId !== dateRequestId) {
				return;
			}
			insights = nextInsights;
		} catch (e: unknown) {
			if (requestId !== dateRequestId) {
				return;
			}
			error = e instanceof Error ? e.message : String(e);
		}
	}

	let trendConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!agg) return null;
		const labels = agg.daily.map((d) => d.date);
		const lowBand = insights?.trend_band.nightly_typical_low ?? null;
		const highBand = insights?.trend_band.nightly_typical_high ?? null;
		const datasets: ChartConfiguration<'line'>['data']['datasets'] = [];

		if (lowBand != null && highBand != null) {
			datasets.push(
				{
					label: 'Typical Low',
					data: labels.map(() => lowBand),
					borderColor: withAlpha(COLORS.hrvWeekly, '80'),
					borderWidth: 1,
					borderDash: [3, 3],
					pointRadius: 0,
					tension: 0,
					fill: false
				},
				{
					label: 'Typical High',
					data: labels.map(() => highBand),
					borderColor: withAlpha(COLORS.hrvWeekly, '80'),
					borderWidth: 1,
					borderDash: [3, 3],
					pointRadius: 0,
					tension: 0,
					fill: '-1',
					backgroundColor: withAlpha(COLORS.hrvWeekly, '14')
				}
			);
		}

		datasets.push(
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
		);

		return {
			type: 'line',
			data: { labels, datasets },
			options: {
				responsive: true,
				maintainAspectRatio: false,
				interaction: { mode: 'index' as const, intersect: false },
				onClick: (_event, elements, chart) => {
					const active = elements[0];
					if (!active) return;
					const label = chart.data.labels?.[active.index];
					if (typeof label !== 'string' || label === selectedDate) return;
					void onDateChange(label);
				},
				plugins: {
					legend: { labels: { boxWidth: 12, font: { size: 11 }, color: '#8a9baa' } },
					tooltip: {
						backgroundColor: '#1a2332',
						borderWidth: 1,
						borderColor: withAlpha(COLORS.hrv, '60'),
						padding: 10,
						cornerRadius: 4
					}
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

	type HrvIntradaySegment = NonNullable<HrvInsights['intraday_segments']>[number];

	function makeIntradayConfig(
		segment: HrvIntradaySegment | null,
		color: string
	): ChartConfiguration<'line'> | null {
		if (!segment || segment.values.length === 0) return null;
		const points = segment.values.filter((value) => Boolean(value.timestamp));
		if (points.length === 0) return null;
		return {
			type: 'line',
			data: {
				labels: points.map((value) => value.timestamp),
				datasets: [
					{
						label: segment.label,
						data: points.map((value) => value.value),
						borderColor: color,
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
					tooltip: {
						backgroundColor: '#1a2332',
						borderWidth: 1,
						borderColor: withAlpha(COLORS.hrv, '60'),
						padding: 10,
						cornerRadius: 4
					}
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
	}

	let intradaySegment = $derived.by(
		() => insights?.intraday_segments.find((segment) => segment.key === 'all') ?? null
	);
	let intradayConfig = $derived.by(() => makeIntradayConfig(intradaySegment, COLORS.hrv));

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

	let dayStats = $derived.by(() => insights?.day_stats ?? null);
	let recovery = $derived.by(() => insights?.recovery ?? null);
	let quality = $derived.by(() => insights?.quality ?? null);
	let statusMix = $derived.by(() => insights?.status_mix ?? []);
	let insightDate = $derived.by(() => insights?.date ?? null);

	function fmtSigned(n: number | null | undefined): string {
		if (n == null) return '-';
		const rounded = n.toFixed(1);
		return n > 0 ? `+${rounded}` : rounded;
	}

	function fmtTimeWindow(start: string | null | undefined, end: string | null | undefined): string {
		if (!start || !end) return '-';
		return `${start.slice(11, 16)}-${end.slice(11, 16)}`;
	}

	function recoveryColorClass(status: string | null | undefined): string {
		if (status === 'suppressed' || status === 'below_baseline') return 'text-[#E85D4A]';
		if (status === 'elevated' || status === 'stable') return 'text-[#4CAF82]';
		return 'text-[#8a9baa]';
	}

	function insightColor(level: string): string {
		if (level === 'warning') return '#E85D4A';
		if (level === 'caution') return '#D4944C';
		if (level === 'good') return '#4CAF82';
		return '#8a9baa';
	}
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
			<StatCard
				title="Balanced"
				value={stats?.balancedPct != null ? stats.balancedPct + '%' : '-'}
				colorClass="text-[#4CAF82]"
				subtitle={`of ${stats?.totalDays ?? 0} days`}
			/>
			<StatCard title="Days Tracked" value={stats?.totalDays ?? '-'} colorClass="text-[#8a9baa]" />
		</div>
	{/if}

	{#if recovery || quality}
		<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
			<StatCard
				title="Nightly vs 7-Day"
				value={fmtSigned(recovery?.delta_nightly_from_baseline)}
				unit="ms"
				subtitle={`baseline ${fmt(recovery?.baseline_nightly_7d)} ms`}
				colorClass={recoveryColorClass(recovery?.status)}
			/>
			<StatCard
				title="Acute vs Weekly"
				value={fmtSigned(recovery?.acute_gap_vs_weekly)}
				unit="ms"
				subtitle="nightly - weekly"
				colorClass={recoveryColorClass(recovery?.status)}
			/>
			<StatCard
				title="Recovery"
				value={recovery?.status ? recovery.status.replace('_', ' ').toUpperCase() : '-'}
				subtitle="server-derived signal"
				colorClass={recoveryColorClass(recovery?.status)}
			/>
			<StatCard
				title="Coverage"
				value={fmtTimeWindow(quality?.coverage_start, quality?.coverage_end)}
				subtitle={`${quality?.sample_count ?? 0} samples`}
				colorClass="text-[#5BB5A6]"
			/>
		</div>
	{/if}

	{#if dayStats}
		<h2 class="text-sm font-semibold text-[#8a9baa] uppercase tracking-wide mb-3">
			Day Snapshot {insightDate ? `— ${insightDate}` : ''}
		</h2>
		<div class="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
			<StatCard title="Nightly" value={fmt(dayStats.nightly_avg)} unit="ms" colorClass="text-[#9B6BCD]" />
			<StatCard title="Weekly" value={fmt(dayStats.weekly_avg)} unit="ms" colorClass="text-[#b794e0]" />
			<StatCard
				title="HRV Status"
				value={dayStats.status ? dayStats.status.toUpperCase() : '-'}
				colorClass="text-[#8a9baa]"
			/>
		</div>
	{/if}

	{#if insights && insights.insights.length > 0}
		<div class="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-5 mb-6">
			<h2 class="text-sm font-semibold text-[#8a9baa] uppercase tracking-wide mb-3">
				Recovery Insights {insightDate ? `— ${insightDate}` : ''}
			</h2>
			<div class="space-y-2">
				{#each insights.insights as item}
					<div
						class="bg-[rgba(255,255,255,0.02)] rounded-md px-3 py-2 border-l-2"
						style="border-left-color: {insightColor(item.level)};"
					>
						<div class="text-[11px] uppercase tracking-wide" style="color: {insightColor(item.level)};">
							{item.level}
						</div>
						<div class="text-sm text-[#d9e5ec] font-medium">{item.title}</div>
						<div class="text-xs text-[#8a9baa]">{item.detail}</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	{#if statusMix.length > 0}
		<div class="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-5 mb-6">
			<h2 class="text-sm font-semibold text-[#8a9baa] uppercase tracking-wide mb-3">
				Status Mix (Recent 14 Days)
			</h2>
			<div class="flex h-6 rounded overflow-hidden mb-2">
				{#each statusMix as bucket}
					<div
						class="flex items-center justify-center text-[10px] font-medium text-white/90"
						style="width:{bucket.pct}%; background-color:{bucket.label === 'Balanced' ? '#4CAF82' : bucket.label === 'Low' ? '#E85D4A' : bucket.label === 'Unbalanced' ? '#D4944C' : '#8a9baa'};"
						title="{bucket.label}: {bucket.count} days ({bucket.pct}%)"
					>
						{#if bucket.pct >= 8}{bucket.pct}%{/if}
					</div>
				{/each}
			</div>
			<div class="flex gap-4 flex-wrap">
				{#each statusMix as bucket}
					<div class="text-xs text-[#8a9baa]">{bucket.label}: {bucket.count}d ({bucket.pct}%)</div>
				{/each}
			</div>
		</div>
	{/if}

	<div class="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-5 mb-6">
		<h2 class="text-sm font-semibold text-[#8a9baa] uppercase tracking-wide mb-3">Daily Trend</h2>
		{#if trendConfig}
			<LineChart config={trendConfig} height={300} />
		{/if}
	</div>

	{#if selectedDate && !insights}
		<div class="text-sm text-[#5e7282]">Loading intraday segments...</div>
	{:else if selectedDate}
		<div class="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-5">
			<h2 class="text-sm font-semibold text-[#8a9baa] uppercase tracking-wide mb-3">
				Overnight HRV — {selectedDate}
			</h2>
			{#if intradayConfig}
				<LineChart config={intradayConfig} height={300} />
				<p class="text-xs text-[#4a5c6a] mt-2">
					{intradaySegment?.sample_count ?? 0} readings • avg {fmt(intradaySegment?.avg)} ms
				</p>
			{:else}
				<div class="text-sm text-[#5e7282]">No HRV samples for this day.</div>
			{/if}
		</div>
	{/if}
{/if}
