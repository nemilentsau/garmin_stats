<script lang="ts">
	import { onMount } from 'svelte';
	import {
		api,
		type DailyAggregates,
		type HeartRateInsights,
		type WellnessData
	} from '$lib/api';
	import { startRealtimePage } from '$lib/realtime-page';
	import LineChart from '$lib/components/LineChart.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import MetricDefinition from '$lib/components/MetricDefinition.svelte';
	import DateSelector from '$lib/components/DateSelector.svelte';
	import { fmt } from '$lib/format';
	import { COLORS, withAlpha } from '$lib/colors';
	import type { ChartConfiguration } from 'chart.js';

	let agg: DailyAggregates | null = $state(null);
	let insights: HeartRateInsights | null = $state(null);
	let intradayData: WellnessData | null = $state(null);
	let selectedDate = $state('');
	let loading = $state(true);
	let error: string | null = $state(null);
	let dateRequestId = 0;

	async function fetchData() {
		const date = selectedDate || undefined;
		const [nextAgg, nextInsights, nextIntraday] = await Promise.all([
			api.getDailyAggregates(),
			api.getHeartRateInsights(date),
			date ? api.getWellness(date) : Promise.resolve<WellnessData | null>(null)
		]);
		if ((selectedDate || undefined) !== date) {
			return;
		}
		agg = nextAgg;
		insights = nextInsights;
		intradayData = nextIntraday;
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
		intradayData = null;
		insights = null;
		const requestId = ++dateRequestId;
		try {
			const [nextInsights, nextIntraday] = await Promise.all([
				api.getHeartRateInsights(date || undefined),
				date ? api.getWellness(date) : Promise.resolve<WellnessData | null>(null)
			]);
			if (requestId !== dateRequestId) {
				return;
			}
			insights = nextInsights;
			intradayData = nextIntraday;
		} catch (e: unknown) {
			if (requestId !== dateRequestId) {
				return;
			}
			error = e instanceof Error ? e.message : String(e);
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
		const labels = agg.daily.map((d) => d.date);
		const typicalLow = agg.period?.heart_rate.typical_low ?? null;
		const typicalHigh = agg.period?.heart_rate.typical_high ?? null;
		const datasets: ChartConfiguration<'line'>['data']['datasets'] = [];

		if (typicalLow != null && typicalHigh != null) {
			datasets.push(
				{
					label: 'Typical Low',
					data: labels.map(() => typicalLow),
					borderColor: withAlpha(COLORS.heartRateResting, '70'),
					borderWidth: 1,
					borderDash: [3, 3],
					pointRadius: 0,
					tension: 0,
					fill: false
				},
				{
					label: 'Typical High',
					data: labels.map(() => typicalHigh),
					borderColor: withAlpha(COLORS.heartRateResting, '70'),
					borderWidth: 1,
					borderDash: [3, 3],
					pointRadius: 0,
					tension: 0,
					fill: '-1',
					backgroundColor: withAlpha(COLORS.heartRateResting, '10')
				}
			);
		}

		datasets.push(
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
		);

		return {
			type: 'line',
			data: {
				labels,
				datasets
			},
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
				plugins: darkPlugins,
				scales: darkScales
			}
		};
	});

	let dayStats = $derived.by(() => {
		return insights?.day_stats ?? null;
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
		if (!insights || insights.zones.length === 0) return null;
		return insights.zones.map((z) => ({
			label: z.label,
			color: ZONE_COLORS[z.label] ?? '#6b7d8e',
			pct: z.pct,
			minutes: z.minutes
		}));
	});

	let recovery = $derived.by(() => insights?.recovery ?? null);
	let quality = $derived.by(() => insights?.quality ?? null);
	let insightDate = $derived.by(() => insights?.date ?? null);

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
		if (status === 'high' || status === 'elevated') return 'text-[#E85D4A]';
		if (status === 'low' || status === 'normal') return 'text-[#4CAF82]';
		return 'text-[#8a9baa]';
	}

	function insightColor(level: string): string {
		if (level === 'warning') return '#E85D4A';
		if (level === 'caution') return '#D4944C';
		if (level === 'good') return '#4CAF82';
		return '#8a9baa';
	}
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

	{#if recovery || quality}
		<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
			<StatCard
				title="RHR vs 7-Day"
				value={fmtSigned(recovery?.delta_from_baseline)}
				unit="bpm"
				subtitle={`baseline ${fmt(recovery?.baseline_resting_7d)} bpm`}
				colorClass={recoveryColorClass(recovery?.status)}
			/>
			<StatCard
				title="Recovery"
				value={recovery?.status ? recovery.status.toUpperCase() : '-'}
				subtitle="server-derived signal"
				colorClass={recoveryColorClass(recovery?.status)}
			/>
			<StatCard
				title="Samples"
				value={quality?.sample_count ?? '-'}
				subtitle={insightDate ? `date ${insightDate}` : ''}
				colorClass="text-[#8a9baa]"
			/>
			<StatCard
				title="Coverage"
				value={fmtTimeWindow(quality?.coverage_start, quality?.coverage_end)}
				subtitle={`${fmt(quality?.coverage_hours)} hrs`}
				colorClass="text-[#5BB5A6]"
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

	{#if dayStats}
		<h2 class="text-sm font-semibold text-[#8a9baa] uppercase tracking-wide mb-3">
			Day Snapshot {insightDate ? `— ${insightDate}` : ''}
		</h2>
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
	{:else if selectedDate}
		<div class="text-sm text-[#5e7282] mb-6">Loading intraday data...</div>
	{/if}

	{#if zoneBreakdown}
		<div class="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-5">
			<h2 class="text-sm font-semibold text-[#8a9baa] uppercase tracking-wide mb-3">
				HR Zones {insightDate ? `— ${insightDate}` : ''}
			</h2>
			<div class="flex h-6 rounded overflow-hidden">
				{#each zoneBreakdown as zone}
					<div
						class="flex items-center justify-center text-[10px] font-medium text-white/90"
						style="width: {zone.pct}%; background-color: {zone.color};"
						title="{zone.label}: {zone.minutes} min ({zone.pct}%)"
					>
						{#if zone.pct >= 8}{zone.pct}%{/if}
					</div>
				{/each}
			</div>
			<div class="flex gap-4 mt-2 flex-wrap">
				{#each zoneBreakdown as zone}
					<div class="flex items-center gap-1.5 text-xs text-[#8a9baa]">
						<span class="inline-block w-2.5 h-2.5 rounded-sm" style="background-color: {zone.color};"></span>
						{zone.label} {fmt(zone.minutes)}m ({zone.pct}%)
					</div>
				{/each}
			</div>
		</div>
	{/if}
{/if}
