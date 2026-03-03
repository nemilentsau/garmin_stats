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
	import StatCard from '$lib/components/StatCard.svelte';
	import MetricDefinition from '$lib/components/MetricDefinition.svelte';
	import DateSelector from '$lib/components/DateSelector.svelte';
	import { fmt, fmtSigned, fmtTimeWindow } from '$lib/format';
	import { COLORS, withAlpha, insightLevelColor } from '$lib/colors';
	import { chartTooltip, DARK_GRID, DARK_GRID_Y, DARK_BORDER, DARK_TICK } from '$lib/chart-setup';
	import type { ChartConfiguration } from 'chart.js';

	let agg: DailyAggregates | null = $state(null);
	let insights: HeartRateInsights | null = $state(null);
	let intradayData: WellnessData | null = $state(null);
	let analysis: HRAnalysis | null = $state(null);
	let distribution: HRDistribution | null = $state(null);
	let selectedDate = $state('');
	let loading = $state(true);
	let error: string | null = $state(null);
	let dateRequestId = 0;

	async function fetchData() {
		const date = selectedDate || undefined;
		const [nextAgg, nextInsights, nextIntraday, nextAnalysis] = await Promise.all([
			api.getDailyAggregates(),
			api.getHeartRateInsights(date),
			date ? api.getWellness(date) : Promise.resolve<WellnessData | null>(null),
			api.getHeartRateAnalysis()
		]);
		if ((selectedDate || undefined) !== date) {
			return;
		}
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
		distribution = null;
		const requestId = ++dateRequestId;
		try {
			const promises: [
				Promise<HeartRateInsights>,
				Promise<WellnessData | null>,
				Promise<HRDistribution | null>
			] = [
				api.getHeartRateInsights(date || undefined),
				date ? api.getWellness(date) : Promise.resolve<WellnessData | null>(null),
				date ? api.getHRDistribution(date) : Promise.resolve<HRDistribution | null>(null)
			];
			const [nextInsights, nextIntraday, nextDistribution] = await Promise.all(promises);
			if (requestId !== dateRequestId) {
				return;
			}
			insights = nextInsights;
			intradayData = nextIntraday;
			distribution = nextDistribution;
		} catch (e: unknown) {
			if (requestId !== dateRequestId) {
				return;
			}
			error = e instanceof Error ? e.message : String(e);
		}
	}

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
					tooltip: chartTooltip(withAlpha(COLORS.heartRate, '60'))
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

	function recoveryColorClass(status: string | null | undefined): string {
		if (status === 'high' || status === 'elevated') return 'text-[#E85D4A]';
		if (status === 'low' || status === 'normal') return 'text-[#4CAF82]';
		return 'text-[#8a9baa]';
	}

	// --- Analysis chart configs ---

	let restingTrendConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!analysis || analysis.resting_hr_trend.length === 0) return null;
		const t = analysis.resting_hr_trend;
		return {
			type: 'line',
			data: {
				labels: t.map((p) => p.date),
				datasets: [
					{
						label: 'Resting HR',
						data: t.map((p) => p.resting_bpm),
						borderColor: withAlpha(COLORS.heartRateResting, '60'),
						borderWidth: 1,
						pointRadius: 2,
						pointBackgroundColor: COLORS.heartRateResting,
						tension: 0,
						spanGaps: true
					},
					{
						label: '7-Day MA',
						data: t.map((p) => p.ma7_bpm),
						borderColor: COLORS.heartRateResting,
						borderWidth: 2.5,
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
				plugins: darkPlugins,
				scales: darkScales
			}
		};
	});

	let distributionConfig = $derived.by<ChartConfiguration<'bar'> | null>(() => {
		if (!distribution || distribution.bins.length === 0) return null;
		return {
			type: 'bar',
			data: {
				labels: distribution.bins.map((b) => `${b.bin_start}-${b.bin_end}`),
				datasets: [
					{
						label: 'Readings',
						data: distribution.bins.map((b) => b.count),
						backgroundColor: withAlpha(COLORS.heartRate, '70'),
						borderColor: COLORS.heartRate,
						borderWidth: 1,
						borderRadius: 2
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: false },
					tooltip: chartTooltip(withAlpha(COLORS.heartRate, '60'))
				},
				scales: {
					x: {
						title: { display: true, text: 'bpm range', ...DARK_TICK },
						ticks: { maxRotation: 45, font: { size: 10 }, ...DARK_TICK },
						grid: DARK_GRID,
						border: DARK_BORDER
					},
					y: {
						beginAtZero: true,
						title: { display: true, text: 'count', ...DARK_TICK },
						ticks: DARK_TICK,
						grid: DARK_GRID_Y,
						border: DARK_BORDER
					}
				}
			}
		};
	});

	let circadianConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!analysis || analysis.circadian_profile.length === 0) return null;
		const profile = analysis.circadian_profile;
		return {
			type: 'line',
			data: {
				labels: profile.map((p) => `${String(p.hour).padStart(2, '0')}:00`),
				datasets: [
					{
						label: 'Avg HR',
						data: profile.map((p) => p.avg_bpm),
						borderColor: COLORS.heartRate,
						borderWidth: 2,
						pointRadius: 3,
						pointBackgroundColor: COLORS.heartRate,
						tension: 0.3,
						fill: { target: 'origin', above: withAlpha(COLORS.heartRate, '15') },
						spanGaps: true
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: false },
					tooltip: chartTooltip(withAlpha(COLORS.heartRate, '60'))
				},
				scales: {
					x: {
						title: { display: true, text: 'Hour of Day', ...DARK_TICK },
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

	let sleepingHRConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!analysis || analysis.sleeping_hr_trend.length === 0) return null;
		const trend = analysis.sleeping_hr_trend;
		return {
			type: 'line',
			data: {
				labels: trend.map((p) => p.date),
				datasets: [
					{
						label: 'Sleeping HR',
						data: trend.map((p) => p.avg_sleeping_bpm),
						borderColor: COLORS.sleep,
						borderWidth: 2,
						pointRadius: 2,
						pointBackgroundColor: COLORS.sleep,
						tension: 0.3,
						spanGaps: true,
						fill: { target: 'origin', above: withAlpha(COLORS.sleep, '1F') }
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: false },
					tooltip: chartTooltip(withAlpha(COLORS.sleep, '99'))
				},
				scales: darkScales
			}
		};
	});

	let boxplotConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!analysis || analysis.weekly_boxplots.length === 0) return null;
		const boxes = analysis.weekly_boxplots;
		const labels = boxes.map((b) => b.iso_week);
		return {
			type: 'line',
			data: {
				labels,
				datasets: [
					{
						label: 'Min',
						data: boxes.map((b) => b.min_bpm),
						borderColor: withAlpha(COLORS.heartRateResting, '50'),
						borderWidth: 1,
						borderDash: [3, 3],
						pointRadius: 0,
						tension: 0,
						fill: false
					},
					{
						label: 'Q1',
						data: boxes.map((b) => b.q1_bpm),
						borderColor: withAlpha(COLORS.heartRateResting, '70'),
						borderWidth: 1,
						pointRadius: 0,
						tension: 0,
						fill: false
					},
					{
						label: 'Median',
						data: boxes.map((b) => b.median_bpm),
						borderColor: COLORS.heartRateResting,
						borderWidth: 2.5,
						pointRadius: 3,
						pointBackgroundColor: COLORS.heartRateResting,
						tension: 0
					},
					{
						label: 'Q3',
						data: boxes.map((b) => b.q3_bpm),
						borderColor: withAlpha(COLORS.heartRateResting, '70'),
						borderWidth: 1,
						pointRadius: 0,
						tension: 0,
						fill: '-2',
						backgroundColor: withAlpha(COLORS.heartRateResting, '12')
					},
					{
						label: 'Max',
						data: boxes.map((b) => b.max_bpm),
						borderColor: withAlpha(COLORS.heartRateResting, '50'),
						borderWidth: 1,
						borderDash: [3, 3],
						pointRadius: 0,
						tension: 0,
						fill: false
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				interaction: { mode: 'index' as const, intersect: false },
				plugins: darkPlugins,
				scales: {
					x: {
						ticks: { maxRotation: 45, font: { size: 10 }, ...DARK_TICK },
						grid: DARK_GRID,
						border: DARK_BORDER
					},
					y: {
						beginAtZero: false,
						title: { display: true, text: 'Resting bpm', ...DARK_TICK },
						ticks: DARK_TICK,
						grid: DARK_GRID_Y,
						border: DARK_BORDER
					}
				}
			}
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

	<MetricDefinition title="Understanding Your Heart Rate">
		<p class="mb-2">
			Your heart rate tells a story about how your body responds to the world. <strong>Resting heart rate</strong>
			(RHR) &mdash; measured when you're calm and still &mdash; is the baseline of that story. A lower RHR
			generally indicates stronger cardiovascular fitness; most adults sit between 60&ndash;100 bpm,
			while trained athletes can drop to 40&ndash;60 bpm.
		</p>
		<p class="mb-2">
			But a single number only tells you where you are <em>today</em>. The charts below unpack the full picture:
		</p>
		<ul class="list-disc list-inside space-y-1 mb-2 text-[#8a9baa]">
			<li><strong>Daily Trend</strong> &mdash; day-to-day avg and resting HR, with IQR bands showing your typical range. Click a day to drill in.</li>
			<li><strong>Intraday</strong> &mdash; every reading across a single day. Reveals exercise spikes, rest valleys, and how quickly you recover.</li>
			<li><strong>HR Zones</strong> &mdash; how your day splits across Rest / Light / Moderate / Vigorous. More time in higher zones means more cardiovascular load.</li>
			<li><strong>Resting HR Trend</strong> &mdash; raw daily resting HR plus a 7-day moving average. The MA line smooths out noise so you can spot gradual drift &mdash; a steady climb can signal overtraining, illness, or accumulated stress.</li>
			<li><strong>HR Distribution</strong> &mdash; a histogram of every reading in a day, binned by 5 bpm. A tight cluster means a quiet day; a wide spread or a second peak means your body shifted gears.</li>
			<li><strong>Circadian Profile</strong> &mdash; your average heart rate for each hour of the day, built from the entire period. The dip in the early-morning hours reflects deep sleep; the rise through midday reflects waking activity. Changes in the shape of this curve can indicate shifting sleep patterns or lifestyle changes.</li>
			<li><strong>Sleeping HR</strong> &mdash; average HR during actual sleep stages (light, deep, REM &mdash; awake periods excluded). This is the purest resting signal your body produces; a rising trend here deserves attention even if daytime resting HR looks stable.</li>
			<li><strong>Weekly Boxplot</strong> &mdash; each ISO week's resting HR summarized as min / Q1 / median / Q3 / max. Lets you compare week-to-week variability at a glance &mdash; a tightening box means your body is settling into a consistent rhythm.</li>
		</ul>
		<p>
			Together, these views let you move from &ldquo;my resting HR is 52&rdquo; to understanding <em>when</em> it
			rises, <em>how</em> your body distributes effort across a day, and <em>whether</em> the trend is heading
			in the right direction.
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
						style="border-left-color: {insightLevelColor(item.level)};"
					>
						<div class="text-[11px] uppercase tracking-wide" style="color: {insightLevelColor(item.level)};">
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
		<div class="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-5 mb-6">
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

	{#if restingTrendConfig}
		<div class="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-5 mb-6">
			<h2 class="text-sm font-semibold text-[#8a9baa] uppercase tracking-wide mb-3">
				Resting HR Trend &mdash; 7-Day Moving Average
			</h2>
			<LineChart config={restingTrendConfig} height={300} />
		</div>
	{/if}

	{#if selectedDate && distributionConfig}
		<div class="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-5 mb-6">
			<h2 class="text-sm font-semibold text-[#8a9baa] uppercase tracking-wide mb-3">
				HR Distribution &mdash; {selectedDate}
			</h2>
			<BarChart config={distributionConfig} height={260} />
			<p class="text-xs text-[#4a5c6a] mt-2">{distribution?.sample_count ?? 0} readings</p>
		</div>
	{/if}

	{#if circadianConfig}
		<div class="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-5 mb-6">
			<h2 class="text-sm font-semibold text-[#8a9baa] uppercase tracking-wide mb-3">
				Circadian HR Profile
			</h2>
			<LineChart config={circadianConfig} height={280} />
			<p class="text-xs text-[#4a5c6a] mt-2">Average heart rate by hour of day across the entire period</p>
		</div>
	{/if}

	{#if sleepingHRConfig}
		<div class="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-5 mb-6">
			<h2 class="text-sm font-semibold text-[#8a9baa] uppercase tracking-wide mb-3">
				Sleeping HR Trend
			</h2>
			<LineChart config={sleepingHRConfig} height={280} />
			<p class="text-xs text-[#4a5c6a] mt-2">Average HR during light/deep/REM sleep stages (excludes awake)</p>
		</div>
	{/if}

	{#if boxplotConfig}
		<div class="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-5 mb-6">
			<h2 class="text-sm font-semibold text-[#8a9baa] uppercase tracking-wide mb-3">
				Weekly Resting HR &mdash; Boxplot
			</h2>
			<LineChart config={boxplotConfig} height={280} />
			<p class="text-xs text-[#4a5c6a] mt-2">Min / Q1 / Median / Q3 / Max of daily resting HR per ISO week</p>
		</div>
	{/if}
{/if}
