<script lang="ts">
	import { onMount } from 'svelte';
	import {
		api,
		type DailyAggregates,
		type HeartRateInsights,
		type HRAnalysis,
		type HRDistribution,
		type WellnessData
	} from '$lib/api';
	import { startRealtimePage } from '$lib/realtime-page';
	import LineChart from '$lib/components/LineChart.svelte';
	import BarChart from '$lib/components/BarChart.svelte';
	import MetricDefinition from '$lib/components/MetricDefinition.svelte';
	import { fmt, fmtSigned, fmtTimeWindow } from '$lib/format';
	import { COLORS, withAlpha, insightLevelColor } from '$lib/colors';
	import { chartTooltip, DARK_GRID, DARK_GRID_Y, DARK_BORDER, DARK_TICK } from '$lib/chart-setup';
	import type { ChartConfiguration } from 'chart.js';

	// ── State ──
	let agg: DailyAggregates | null = $state(null);
	let insights: HeartRateInsights | null = $state(null);
	let intradayData: WellnessData | null = $state(null);
	let analysis: HRAnalysis | null = $state(null);
	let distribution: HRDistribution | null = $state(null);
	let selectedDate = $state('');
	let loading = $state(true);
	let error: string | null = $state(null);
	let dateRequestId = 0;
	let activeTab: 'today' | 'trends' | 'sleep' | 'analysis' = $state('today');

	// ── Data fetching ──
	async function fetchData() {
		const date = selectedDate || undefined;
		const [nextAgg, nextInsights, nextIntraday, nextAnalysis] = await Promise.all([
			api.getDailyAggregates(),
			api.getHeartRateInsights(date),
			date ? api.getWellness(date) : Promise.resolve<WellnessData | null>(null),
			api.getHeartRateAnalysis()
		]);
		if ((selectedDate || undefined) !== date) return;
		agg = nextAgg;
		insights = nextInsights;
		intradayData = nextIntraday;
		analysis = nextAnalysis;
		if (date) {
			distribution = await api.getHRDistribution(date);
		}
	}

	onMount(() => {
		return startRealtimePage({
			fetchData,
			setError: (message) => { error = message; },
			setLoading: (value) => { loading = value; }
		});
	});

	async function onDateChange(date: string) {
		selectedDate = date;
		intradayData = null;
		insights = null;
		distribution = null;
		if (date && activeTab !== 'today') activeTab = 'today';
		const requestId = ++dateRequestId;
		try {
			const [nextInsights, nextIntraday, nextDistribution] = await Promise.all([
				api.getHeartRateInsights(date || undefined),
				date ? api.getWellness(date) : Promise.resolve<WellnessData | null>(null),
				date ? api.getHRDistribution(date) : Promise.resolve<HRDistribution | null>(null)
			]);
			if (requestId !== dateRequestId) return;
			insights = nextInsights;
			intradayData = nextIntraday;
			distribution = nextDistribution;
		} catch (e: unknown) {
			if (requestId !== dateRequestId) return;
			error = e instanceof Error ? e.message : String(e);
		}
	}

	// ── Day navigation ──
	function navigateDay(direction: -1 | 1) {
		if (!agg) return;
		const days = agg.days;
		if (!selectedDate) {
			// Select last day if navigating from "All"
			if (days.length > 0) void onDateChange(days[days.length - 1]);
			return;
		}
		const idx = days.indexOf(selectedDate);
		const next = idx + direction;
		if (next >= 0 && next < days.length) {
			void onDateChange(days[next]);
		}
	}

	// ── Derived data ──
	let dayStats = $derived.by(() => insights?.day_stats ?? null);
	let recovery = $derived.by(() => insights?.recovery ?? null);
	let quality = $derived.by(() => insights?.quality ?? null);
	let insightDate = $derived.by(() => insights?.date ?? null);

	let stats = $derived.by(() => {
		if (!agg?.period) return null;
		const hr = agg.period.heart_rate;
		return { overallAvg: hr.avg, typicalLow: hr.typical_low, typicalHigh: hr.typical_high, avgResting: hr.avg_resting };
	});

	let zoneBreakdown = $derived.by(() => {
		if (!insights || insights.zones.length === 0) return null;
		return insights.zones.map((z) => ({
			label: z.label,
			color: ZONE_COLORS[z.label] ?? '#6b7d8e',
			pct: z.pct,
			minutes: z.minutes
		}));
	});

	// Map recovery status → color for the day strip
	let dayRecoveryMap = $derived.by(() => {
		if (!agg) return new Map<string, string>();
		const map = new Map<string, string>();
		// We'll color based on resting HR relative to period avg
		const avgResting = agg.period?.heart_rate.avg_resting;
		if (avgResting == null) return map;
		for (const d of agg.daily) {
			const rhr = d.heart_rate.resting;
			if (rhr == null) { map.set(d.date, '#3a4a5a'); continue; }
			const delta = rhr - avgResting;
			if (delta > 5) map.set(d.date, '#E85D4A');       // elevated
			else if (delta > 2) map.set(d.date, '#D4944C');  // slightly high
			else map.set(d.date, '#4CAF82');                  // normal/good
		}
		return map;
	});

	// Can navigate prev/next?
	let canPrev = $derived.by(() => {
		if (!agg || !selectedDate) return false;
		return agg.days.indexOf(selectedDate) > 0;
	});
	let canNext = $derived.by(() => {
		if (!agg || !selectedDate) return false;
		return agg.days.indexOf(selectedDate) < agg.days.length - 1;
	});

	// ── Helpers ──
	const ZONE_COLORS: Record<string, string> = {
		Rest: '#4A6FA5', Light: '#4CAF82', Moderate: '#D4944C', Vigorous: '#E85D4A'
	};

	function recoveryColor(status: string | null | undefined): string {
		if (status === 'high' || status === 'elevated') return '#E85D4A';
		if (status === 'low' || status === 'normal') return '#4CAF82';
		return '#8a9baa';
	}

	// ── Shared chart config ──
	const darkScales = {
		x: {
			ticks: { maxRotation: 45, font: { size: 10 }, ...DARK_TICK },
			grid: DARK_GRID,
			border: DARK_BORDER
		},
		y: {
			beginAtZero: false,
			title: { display: true, text: 'bpm', ...DARK_TICK },
			ticks: DARK_TICK,
			grid: DARK_GRID_Y,
			border: DARK_BORDER
		}
	} as const;

	const darkPlugins = {
		legend: { labels: { boxWidth: 12, font: { size: 11 }, color: '#8a9baa' } },
		tooltip: chartTooltip(withAlpha(COLORS.heartRate, '60'))
	} as const;

	// ── Chart: Intraday with zone shading ──
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
				fill: false
			}
		];
		if (dayStats?.resting != null) {
			datasets.push({
				label: 'Resting HR',
				data: intradayData.heart_rate.map(() => dayStats!.resting!),
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
					tooltip: chartTooltip(withAlpha(COLORS.heartRate, '60')),
					annotation: {
						annotations: {
							restZone: { type: 'box', yMin: 0, yMax: 60, backgroundColor: withAlpha(COLORS.zoneRest, '0F'), borderWidth: 0, adjustScaleRange: false },
							lightZone: { type: 'box', yMin: 60, yMax: 100, backgroundColor: withAlpha(COLORS.heartRateResting, '0D'), borderWidth: 0, adjustScaleRange: false },
							modZone: { type: 'box', yMin: 100, yMax: 140, backgroundColor: withAlpha(COLORS.stress, '0D'), borderWidth: 0, adjustScaleRange: false },
							vigZone: { type: 'box', yMin: 140, yMax: 220, backgroundColor: withAlpha(COLORS.heartRate, '0D'), borderWidth: 0, adjustScaleRange: false }
						}
					}
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
						title: { display: true, text: 'bpm', ...DARK_TICK },
						ticks: DARK_TICK,
						grid: DARK_GRID_Y,
						border: DARK_BORDER
					}
				}
			}
		};
	});

	// ── Chart: Trend ──
	let trendConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!agg) return null;
		const labels = agg.daily.map((d) => d.date);
		const typicalLow = agg.period?.heart_rate.typical_low ?? null;
		const typicalHigh = agg.period?.heart_rate.typical_high ?? null;
		const datasets: ChartConfiguration<'line'>['data']['datasets'] = [];

		if (typicalLow != null && typicalHigh != null) {
			datasets.push(
				{
					label: 'Typical Low', data: labels.map(() => typicalLow),
					borderColor: withAlpha(COLORS.heartRateResting, '70'), borderWidth: 1, borderDash: [3, 3],
					pointRadius: 0, tension: 0, fill: false
				},
				{
					label: 'Typical High', data: labels.map(() => typicalHigh),
					borderColor: withAlpha(COLORS.heartRateResting, '70'), borderWidth: 1, borderDash: [3, 3],
					pointRadius: 0, tension: 0, fill: '-1', backgroundColor: withAlpha(COLORS.heartRateResting, '10')
				}
			);
		}
		datasets.push(
			{
				label: 'Avg HR', data: agg.daily.map((d) => d.heart_rate.avg),
				borderColor: COLORS.heartRate, borderWidth: 2, pointRadius: 2, tension: 0.3, spanGaps: true
			},
			{
				label: 'Resting HR', data: agg.daily.map((d) => d.heart_rate.resting),
				borderColor: COLORS.heartRateResting, borderWidth: 2, pointRadius: 2, tension: 0.3, spanGaps: true
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
				plugins: darkPlugins,
				scales: darkScales
			}
		};
	});

	// ── Chart: Resting HR trend ──
	let restingTrendConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!analysis || analysis.resting_hr_trend.length === 0) return null;
		const t = analysis.resting_hr_trend;
		return {
			type: 'line',
			data: {
				labels: t.map((p) => p.date),
				datasets: [
					{
						label: 'Resting HR', data: t.map((p) => p.resting_bpm),
						borderColor: withAlpha(COLORS.heartRateResting, '60'), borderWidth: 1,
						pointRadius: 2, pointBackgroundColor: COLORS.heartRateResting, tension: 0, spanGaps: true
					},
					{
						label: '7-Day MA', data: t.map((p) => p.ma7_bpm),
						borderColor: COLORS.heartRateResting, borderWidth: 2.5,
						pointRadius: 0, tension: 0.3, spanGaps: true
					}
				]
			},
			options: {
				responsive: true, maintainAspectRatio: false,
				interaction: { mode: 'index' as const, intersect: false },
				plugins: darkPlugins, scales: darkScales
			}
		};
	});

	// ── Chart: Sleeping HR ──
	let sleepingHRConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!analysis || analysis.sleeping_hr_trend.length === 0) return null;
		const trend = analysis.sleeping_hr_trend;
		return {
			type: 'line',
			data: {
				labels: trend.map((p) => p.date),
				datasets: [{
					label: 'Sleeping HR', data: trend.map((p) => p.avg_sleeping_bpm),
					borderColor: COLORS.sleep, borderWidth: 2, pointRadius: 2,
					pointBackgroundColor: COLORS.sleep, tension: 0.3, spanGaps: true,
					fill: { target: 'origin', above: withAlpha(COLORS.sleep, '1F') }
				}]
			},
			options: {
				responsive: true, maintainAspectRatio: false,
				plugins: { legend: { display: false }, tooltip: chartTooltip(withAlpha(COLORS.sleep, '99')) },
				scales: darkScales
			}
		};
	});

	// ── Chart: Circadian ──
	let circadianConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!analysis || analysis.circadian_profile.length === 0) return null;
		const profile = analysis.circadian_profile;
		return {
			type: 'line',
			data: {
				labels: profile.map((p) => `${String(p.hour).padStart(2, '0')}:00`),
				datasets: [{
					label: 'Avg HR', data: profile.map((p) => p.avg_bpm),
					borderColor: COLORS.heartRate, borderWidth: 2, pointRadius: 3,
					pointBackgroundColor: COLORS.heartRate, tension: 0.3,
					fill: { target: 'origin', above: withAlpha(COLORS.heartRate, '15') }, spanGaps: true
				}]
			},
			options: {
				responsive: true, maintainAspectRatio: false,
				plugins: { legend: { display: false }, tooltip: chartTooltip(withAlpha(COLORS.heartRate, '60')) },
				scales: {
					x: { title: { display: true, text: 'Hour of Day', ...DARK_TICK }, ticks: { font: { size: 10 }, ...DARK_TICK }, grid: DARK_GRID, border: DARK_BORDER },
					y: { beginAtZero: false, title: { display: true, text: 'bpm', ...DARK_TICK }, ticks: DARK_TICK, grid: DARK_GRID_Y, border: DARK_BORDER }
				}
			}
		};
	});

	// ── Chart: Distribution ──
	let distributionConfig = $derived.by<ChartConfiguration<'bar'> | null>(() => {
		if (!distribution || distribution.bins.length === 0) return null;
		return {
			type: 'bar',
			data: {
				labels: distribution.bins.map((b) => `${b.bin_start}–${b.bin_end}`),
				datasets: [{
					label: 'Readings', data: distribution.bins.map((b) => b.count),
					backgroundColor: withAlpha(COLORS.heartRate, '70'), borderColor: COLORS.heartRate,
					borderWidth: 1, borderRadius: 2
				}]
			},
			options: {
				responsive: true, maintainAspectRatio: false,
				plugins: { legend: { display: false }, tooltip: chartTooltip(withAlpha(COLORS.heartRate, '60')) },
				scales: {
					x: { title: { display: true, text: 'bpm range', ...DARK_TICK }, ticks: { maxRotation: 45, font: { size: 10 }, ...DARK_TICK }, grid: DARK_GRID, border: DARK_BORDER },
					y: { beginAtZero: true, title: { display: true, text: 'count', ...DARK_TICK }, ticks: DARK_TICK, grid: DARK_GRID_Y, border: DARK_BORDER }
				}
			}
		};
	});

	// ── Chart: Weekly Boxplot ──
	let boxplotConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!analysis || analysis.weekly_boxplots.length === 0) return null;
		const boxes = analysis.weekly_boxplots;
		const labels = boxes.map((b) => b.iso_week);
		return {
			type: 'line',
			data: {
				labels,
				datasets: [
					{ label: 'Min', data: boxes.map((b) => b.min_bpm), borderColor: withAlpha(COLORS.heartRateResting, '50'), borderWidth: 1, borderDash: [3, 3], pointRadius: 0, tension: 0, fill: false },
					{ label: 'Q1', data: boxes.map((b) => b.q1_bpm), borderColor: withAlpha(COLORS.heartRateResting, '70'), borderWidth: 1, pointRadius: 0, tension: 0, fill: false },
					{ label: 'Median', data: boxes.map((b) => b.median_bpm), borderColor: COLORS.heartRateResting, borderWidth: 2.5, pointRadius: 3, pointBackgroundColor: COLORS.heartRateResting, tension: 0 },
					{ label: 'Q3', data: boxes.map((b) => b.q3_bpm), borderColor: withAlpha(COLORS.heartRateResting, '70'), borderWidth: 1, pointRadius: 0, tension: 0, fill: '-2', backgroundColor: withAlpha(COLORS.heartRateResting, '12') },
					{ label: 'Max', data: boxes.map((b) => b.max_bpm), borderColor: withAlpha(COLORS.heartRateResting, '50'), borderWidth: 1, borderDash: [3, 3], pointRadius: 0, tension: 0, fill: false }
				]
			},
			options: {
				responsive: true, maintainAspectRatio: false,
				interaction: { mode: 'index' as const, intersect: false },
				plugins: darkPlugins,
				scales: {
					x: { ticks: { maxRotation: 45, font: { size: 10 }, ...DARK_TICK }, grid: DARK_GRID, border: DARK_BORDER },
					y: { beginAtZero: false, title: { display: true, text: 'Resting bpm', ...DARK_TICK }, ticks: DARK_TICK, grid: DARK_GRID_Y, border: DARK_BORDER }
				}
			}
		};
	});
</script>

<svelte:head><title>Heart Rate — Garmin Stats</title></svelte:head>

{#if error}
	<div class="card" style="border-color: rgba(232,93,74,0.3); background: rgba(232,93,74,0.08);">
		<p class="text-[#E85D4A]">Error: {error}</p>
	</div>
{:else if loading}
	<div class="flex items-center justify-center h-64">
		<div class="text-[#5e7282]">Loading...</div>
	</div>
{:else if agg}

	<!-- ─── Top Stat Bar ─── -->
	<div class="stat-bar">
		<div class="stat-item">
			<span class="stat-label">Resting HR</span>
			<span class="stat-value" style="color: #4CAF82;">
				{fmt(stats?.avgResting)}
			</span>
			<span class="stat-unit">bpm</span>
			{#if recovery?.delta_from_baseline != null}
				<span class="stat-delta" style="color: {recoveryColor(recovery?.status)};">
					{fmtSigned(recovery.delta_from_baseline)} vs 7d
				</span>
			{/if}
		</div>
		<div class="stat-item">
			<span class="stat-label">Recovery</span>
			<span class="recovery-pill" style="background: {recoveryColor(recovery?.status)}20; color: {recoveryColor(recovery?.status)}; border-color: {recoveryColor(recovery?.status)}40;">
				{recovery?.status ? recovery.status.toUpperCase() : '-'}
			</span>
		</div>
		<div class="stat-item">
			<span class="stat-label">Daily Avg</span>
			<span class="stat-value" style="color: #E85D4A;">
				{fmt(dayStats?.avg ?? stats?.overallAvg)}
			</span>
			<span class="stat-unit">bpm</span>
		</div>
		<div class="stat-item">
			<span class="stat-label">Range</span>
			<span class="stat-value" style="color: #c8d6e0;">
				{fmt(stats?.typicalLow)}–{fmt(stats?.typicalHigh)}
			</span>
			<span class="stat-unit">bpm</span>
		</div>
	</div>

	<!-- ─── Insight line ─── -->
	{#if insights && insights.insights.length > 0}
		{@const topInsight = insights.insights[0]}
		<div class="insight-line">
			<span class="insight-dot" style="background: {insightLevelColor(topInsight.level)};"></span>
			<span class="insight-level" style="color: {insightLevelColor(topInsight.level)};">{topInsight.level.toUpperCase()}</span>
			<span class="insight-text">{topInsight.title}</span>
			<span class="insight-detail">{topInsight.detail}</span>
		</div>
	{/if}

	<!-- ─── Day selector strip ─── -->
	<div class="day-nav">
		<div class="day-nav-controls">
			<button class="nav-arrow" disabled={!canPrev} onclick={() => navigateDay(-1)}>←</button>
			<button class="day-label" onclick={() => onDateChange('')}>
				{selectedDate || 'All Days'}
			</button>
			<button class="nav-arrow" disabled={!canNext} onclick={() => navigateDay(1)}>→</button>
		</div>
		<div class="day-strip-container">
			<div class="day-strip">
				{#each agg.days as day}
					<button
						class="day-cell"
						class:selected={day === selectedDate}
						style="background: {dayRecoveryMap.get(day) ?? '#3a4a5a'};"
						title={day}
						onclick={() => onDateChange(day === selectedDate ? '' : day)}
					></button>
				{/each}
			</div>
			<div class="day-strip-legend">
				<span><i class="legend-dot" style="background:#4CAF82;"></i>Normal</span>
				<span><i class="legend-dot" style="background:#D4944C;"></i>Elevated</span>
				<span><i class="legend-dot" style="background:#E85D4A;"></i>High</span>
			</div>
		</div>
	</div>

	<!-- ─── Tab bar ─── -->
	<div class="tab-bar">
		<button class="tab" class:active={activeTab === 'today'} onclick={() => activeTab = 'today'}>Today</button>
		<button class="tab" class:active={activeTab === 'trends'} onclick={() => activeTab = 'trends'}>Trends</button>
		<button class="tab" class:active={activeTab === 'sleep'} onclick={() => activeTab = 'sleep'}>Sleep HR</button>
		<button class="tab" class:active={activeTab === 'analysis'} onclick={() => activeTab = 'analysis'}>Analysis</button>
	</div>

	<!-- ─── TAB: Today ─── -->
	{#if activeTab === 'today'}
		{#if selectedDate && intradayConfig}
			<div class="card">
				<h2 class="card-title">Intraday Heart Rate — {selectedDate}</h2>
				<LineChart config={intradayConfig} height={320} />
				<p class="card-footnote">{intradayData?.heart_rate.length ?? 0} readings</p>
			</div>
		{:else if selectedDate}
			<div class="text-sm text-[#5e7282] mb-6">Loading intraday data...</div>
		{:else if trendConfig}
			<div class="card">
				<h2 class="card-title">Daily Trend — Click a day to drill in</h2>
				<LineChart config={trendConfig} height={320} />
			</div>
		{/if}

		{#if zoneBreakdown}
			<div class="zones-stats-row">
				<div class="card zones-card">
					<h2 class="card-title">HR Zones</h2>
					<div class="zone-bar">
						{#each zoneBreakdown as zone}
							<div
								class="zone-segment"
								style="width: {zone.pct}%; background-color: {zone.color};"
								title="{zone.label}: {zone.minutes}m ({zone.pct}%)"
							>
								{#if zone.pct >= 8}<span class="zone-pct">{zone.pct}%</span>{/if}
							</div>
						{/each}
					</div>
					<div class="zone-legend">
						{#each zoneBreakdown as zone}
							<span class="zone-item">
								<i class="legend-dot" style="background: {zone.color};"></i>
								{zone.label} {fmt(zone.minutes)}m
							</span>
						{/each}
					</div>
				</div>
				{#if dayStats}
					<div class="card day-stats-card">
						<h2 class="card-title">Day Stats</h2>
						<div class="mini-stat-grid">
							<div class="mini-stat"><span class="mini-label">Min</span><span class="mini-value" style="color:#4A90D9">{fmt(dayStats.min)}</span></div>
							<div class="mini-stat"><span class="mini-label">Max</span><span class="mini-value" style="color:#D4944C">{fmt(dayStats.max)}</span></div>
							<div class="mini-stat"><span class="mini-label">Avg</span><span class="mini-value" style="color:#E85D4A">{fmt(dayStats.avg)}</span></div>
							<div class="mini-stat"><span class="mini-label">Median</span><span class="mini-value">{fmt(dayStats.median)}</span></div>
							<div class="mini-stat"><span class="mini-label">Resting</span><span class="mini-value" style="color:#4CAF82">{fmt(dayStats.resting)}</span></div>
						</div>
					</div>
				{/if}
			</div>
		{/if}

		{#if insights && insights.insights.length > 0}
			<div class="card">
				<h2 class="card-title">Recovery Insights</h2>
				<div class="insights-list">
					{#each insights.insights as item}
						<div class="insight-card" style="border-left-color: {insightLevelColor(item.level)};">
							<div class="insight-card-level" style="color: {insightLevelColor(item.level)};">{item.level}</div>
							<div class="insight-card-title">{item.title}</div>
							<div class="insight-card-detail">{item.detail}</div>
						</div>
					{/each}
				</div>
			</div>
		{/if}

	<!-- ─── TAB: Trends ─── -->
	{:else if activeTab === 'trends'}
		{#if trendConfig}
			<div class="card">
				<h2 class="card-title">Daily Trend — Avg & Resting HR</h2>
				<LineChart config={trendConfig} height={320} />
			</div>
		{/if}

		{#if restingTrendConfig}
			<div class="card">
				<h2 class="card-title">Resting HR Trend — 7-Day Moving Average</h2>
				<LineChart config={restingTrendConfig} height={280} />
			</div>
		{/if}

	<!-- ─── TAB: Sleep HR ─── -->
	{:else if activeTab === 'sleep'}
		{#if sleepingHRConfig}
			<div class="card">
				<h2 class="card-title">Sleeping HR Trend</h2>
				<LineChart config={sleepingHRConfig} height={300} />
				<p class="card-footnote">Average HR during light/deep/REM sleep stages (excludes awake)</p>
			</div>
		{/if}

		{#if circadianConfig}
			<div class="card">
				<h2 class="card-title">Circadian HR Profile</h2>
				<LineChart config={circadianConfig} height={280} />
				<p class="card-footnote">Average heart rate by hour of day across the entire period</p>
			</div>
		{/if}

	<!-- ─── TAB: Analysis ─── -->
	{:else if activeTab === 'analysis'}
		{#if selectedDate && distributionConfig}
			<div class="card">
				<h2 class="card-title">HR Distribution — {selectedDate}</h2>
				<BarChart config={distributionConfig} height={260} />
				<p class="card-footnote">{distribution?.sample_count ?? 0} readings</p>
			</div>
		{:else if !selectedDate}
			<p class="text-sm text-[#5e7282] mb-4">Select a day to see its HR distribution.</p>
		{/if}

		{#if boxplotConfig}
			<div class="card">
				<h2 class="card-title">Weekly Resting HR — Boxplot</h2>
				<LineChart config={boxplotConfig} height={280} />
				<p class="card-footnote">Min / Q1 / Median / Q3 / Max of daily resting HR per ISO week</p>
			</div>
		{/if}
	{/if}

	<MetricDefinition title="What is Heart Rate?">
		<p>
			Resting heart rate (RHR) is measured when you're calm and still — a lower RHR generally indicates
			stronger cardiovascular fitness. Most adults sit between 60–100 bpm; trained athletes can drop to 40–60 bpm.
			The charts above unpack the full picture: daily trends, intraday patterns, sleep recovery, and statistical analysis.
		</p>
	</MetricDefinition>
{/if}

<style>
	/* ── Stat Bar ── */
	.stat-bar {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 1px;
		background: rgba(255,255,255,0.06);
		border-radius: 10px;
		overflow: hidden;
		margin-bottom: 12px;
	}
	.stat-item {
		background: rgba(13,21,32,0.95);
		padding: 16px 20px;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 2px;
	}
	.stat-label {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 1.5px;
		color: #6b7d8e;
	}
	.stat-value {
		font-family: 'DM Mono', monospace;
		font-size: 28px;
		font-weight: 500;
		line-height: 1.1;
	}
	.stat-unit {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #4a5c6a;
	}
	.stat-delta {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		margin-top: 2px;
	}

	/* Recovery pill */
	.recovery-pill {
		font-family: 'DM Mono', monospace;
		font-size: 16px;
		font-weight: 600;
		letter-spacing: 2px;
		padding: 4px 14px;
		border-radius: 20px;
		border: 1px solid;
		margin-top: 4px;
	}

	/* ── Insight line ── */
	.insight-line {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px 14px;
		background: rgba(255,255,255,0.02);
		border: 1px solid rgba(255,255,255,0.05);
		border-radius: 8px;
		margin-bottom: 12px;
		flex-wrap: wrap;
	}
	.insight-dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		flex-shrink: 0;
	}
	.insight-level {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 1px;
		font-weight: 500;
	}
	.insight-text {
		font-size: 13px;
		color: #d9e5ec;
		font-weight: 500;
	}
	.insight-detail {
		font-size: 12px;
		color: #6b7d8e;
	}

	/* ── Day strip ── */
	.day-nav {
		display: flex;
		align-items: center;
		gap: 14px;
		margin-bottom: 14px;
	}
	.day-nav-controls {
		display: flex;
		align-items: center;
		gap: 4px;
		flex-shrink: 0;
	}
	.nav-arrow {
		width: 28px;
		height: 28px;
		border-radius: 6px;
		border: 1px solid rgba(255,255,255,0.1);
		background: rgba(255,255,255,0.03);
		color: #8a9baa;
		cursor: pointer;
		font-size: 13px;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.15s;
	}
	.nav-arrow:hover:not(:disabled) { background: rgba(255,255,255,0.08); color: #c8d6e0; }
	.nav-arrow:disabled { opacity: 0.3; cursor: default; }

	.day-label {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #c8d6e0;
		background: rgba(255,255,255,0.05);
		border: 1px solid rgba(255,255,255,0.1);
		border-radius: 6px;
		padding: 4px 10px;
		cursor: pointer;
		min-width: 100px;
		text-align: center;
	}
	.day-label:hover { background: rgba(255,255,255,0.08); }

	.day-strip-container {
		flex: 1;
		overflow: hidden;
	}
	.day-strip {
		display: flex;
		gap: 2px;
		overflow-x: auto;
		scrollbar-width: none;
		padding: 2px 0;
	}
	.day-strip::-webkit-scrollbar { display: none; }

	.day-cell {
		width: 8px;
		min-width: 8px;
		height: 22px;
		border-radius: 2px;
		border: none;
		cursor: pointer;
		transition: all 0.12s;
		opacity: 0.7;
	}
	.day-cell:hover { opacity: 1; transform: scaleY(1.3); }
	.day-cell.selected {
		opacity: 1;
		outline: 2px solid #e8f0f5;
		outline-offset: 1px;
		transform: scaleY(1.4);
	}

	.day-strip-legend {
		display: flex;
		gap: 12px;
		margin-top: 4px;
	}
	.day-strip-legend span {
		font-size: 10px;
		color: #5e7282;
		display: flex;
		align-items: center;
		gap: 4px;
	}
	.legend-dot {
		display: inline-block;
		width: 7px;
		height: 7px;
		border-radius: 2px;
	}

	/* ── Tab bar ── */
	.tab-bar {
		display: flex;
		gap: 2px;
		margin-bottom: 16px;
		background: rgba(255,255,255,0.03);
		border-radius: 8px;
		padding: 3px;
	}
	.tab {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		padding: 7px 18px;
		border-radius: 6px;
		border: none;
		background: transparent;
		color: #6b7d8e;
		cursor: pointer;
		transition: all 0.15s;
	}
	.tab:hover { color: #c8d6e0; background: rgba(255,255,255,0.04); }
	.tab.active {
		color: #e8f0f5;
		background: rgba(255,255,255,0.08);
		font-weight: 500;
	}

	/* ── Cards ── */
	.card {
		background: rgba(255,255,255,0.02);
		border: 1px solid rgba(255,255,255,0.05);
		border-radius: 10px;
		padding: 20px;
		margin-bottom: 14px;
	}
	.card-title {
		font-size: 12px;
		font-weight: 600;
		color: #8a9baa;
		text-transform: uppercase;
		letter-spacing: 1px;
		margin-bottom: 14px;
	}
	.card-footnote {
		font-size: 11px;
		color: #4a5c6a;
		margin-top: 8px;
	}

	/* ── Zones + Stats row ── */
	.zones-stats-row {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: 14px;
		margin-bottom: 0;
	}
	.zones-card { margin-bottom: 0; }
	.day-stats-card { margin-bottom: 0; min-width: 180px; }

	.zone-bar {
		display: flex;
		height: 24px;
		border-radius: 4px;
		overflow: hidden;
	}
	.zone-segment {
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.2s;
	}
	.zone-pct {
		font-size: 10px;
		font-weight: 600;
		color: rgba(255,255,255,0.9);
	}
	.zone-legend {
		display: flex;
		gap: 12px;
		margin-top: 10px;
		flex-wrap: wrap;
	}
	.zone-item {
		font-size: 11px;
		color: #8a9baa;
		display: flex;
		align-items: center;
		gap: 5px;
	}

	/* ── Mini stat grid ── */
	.mini-stat-grid {
		display: grid;
		gap: 8px;
	}
	.mini-stat {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 4px 0;
		border-bottom: 1px solid rgba(255,255,255,0.04);
	}
	.mini-stat:last-child { border-bottom: none; }
	.mini-label {
		font-size: 12px;
		color: #6b7d8e;
	}
	.mini-value {
		font-family: 'DM Mono', monospace;
		font-size: 16px;
		font-weight: 500;
		color: #c8d6e0;
	}

	/* ── Insights list ── */
	.insights-list {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.insight-card {
		background: rgba(255,255,255,0.02);
		border-radius: 6px;
		padding: 10px 14px;
		border-left: 2px solid;
	}
	.insight-card-level {
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 1px;
		font-weight: 500;
	}
	.insight-card-title {
		font-size: 13px;
		color: #d9e5ec;
		font-weight: 500;
		margin-top: 2px;
	}
	.insight-card-detail {
		font-size: 12px;
		color: #6b7d8e;
		margin-top: 2px;
	}

	/* ── Responsive ── */
	@media (max-width: 768px) {
		.stat-bar { grid-template-columns: repeat(2, 1fr); }
		.zones-stats-row { grid-template-columns: 1fr; }
		.day-nav { flex-direction: column; align-items: stretch; }
	}
</style>
