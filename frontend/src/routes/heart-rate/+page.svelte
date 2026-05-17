<script lang="ts">
	import { onMount } from 'svelte';
	import { slide } from 'svelte/transition';
	import {
		api,
		type HeartRateDaily,
		type HeartRateRawData,
		type HeartRateInsights,
		type HRAnalysis,
		type HRDistribution
	} from '$lib/api';
	import { startRealtimePage } from '$lib/realtime-page';
	import LineChart from '$lib/components/LineChart.svelte';
	import BarChart from '$lib/components/BarChart.svelte';
	import PolarAreaChart from '$lib/components/PolarAreaChart.svelte';

	import MetricDefinition from '$lib/components/MetricDefinition.svelte';
	import { fmt, fmtSigned } from '$lib/format';
	import { COLORS, withAlpha, insightLevelColor } from '$lib/colors';
	import { chartTooltip, DARK_GRID, DARK_GRID_Y, DARK_BORDER, DARK_TICK } from '$lib/chart-setup';
	import TrendRangePicker from '$lib/components/TrendRangePicker.svelte';
	import { localDateIso } from '$lib/date';
	import { type TrendRange, trendCutoff, filterByRange, PERIOD_KEY_MAP } from '$lib/trend-range';
	import type { ChartConfiguration } from 'chart.js';

	// ── State ──
	let agg: HeartRateDaily | null = $state(null);
	let analysis: HRAnalysis | null = $state(null);
	let loading = $state(true);
	let error: string | null = $state(null);
	let trendRange: TrendRange = $state('3M');

	// Latest day (Tier 1 — always the most recent)
	let latestInsights: HeartRateInsights | null = $state(null);
	let latestIntraday: HeartRateRawData | null = $state(null);
	let latestDistribution: HRDistribution | null = $state(null);

	// Historical day (Tier 2 — selected via bar)
	let selectedDate = $state('');
	let historyOpen = $state(false);
	let historicalInsights: HeartRateInsights | null = $state(null);
	let historicalIntraday: HeartRateRawData | null = $state(null);
	let historicalDistribution: HRDistribution | null = $state(null);
	let dateRequestId = 0;

	// ── Data fetching ──
	async function fetchData() {
		const [nextAgg, nextAnalysis] = await Promise.all([
			api.getHeartRateDaily(),
			api.getHeartRateAnalysis()
		]);
		agg = nextAgg;
		analysis = nextAnalysis;

		// Always fetch latest day data for Tier 1
		if (nextAgg.days.length > 0) {
			const latest = nextAgg.days[nextAgg.days.length - 1];
			const [ins, intra, dist] = await Promise.all([
				api.getHeartRateInsights(latest),
				api.getHeartRateRaw(latest),
				api.getHRDistribution(latest)
			]);
			latestInsights = ins;
			latestIntraday = intra;
			latestDistribution = dist;
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
		if (date === '') {
			selectedDate = '';
			historyOpen = false;
			historicalInsights = null;
			historicalIntraday = null;
			historicalDistribution = null;
			return;
		}
		selectedDate = date;
		historyOpen = true;
		historicalInsights = null;
		historicalIntraday = null;
		historicalDistribution = null;
		const requestId = ++dateRequestId;
		try {
			const [nextInsights, nextIntraday, nextDistribution] = await Promise.all([
				api.getHeartRateInsights(date),
				api.getHeartRateRaw(date),
				api.getHRDistribution(date)
			]);
			if (requestId !== dateRequestId) return;
			historicalInsights = nextInsights;
			historicalIntraday = nextIntraday;
			historicalDistribution = nextDistribution;
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
			if (days.length > 0) void onDateChange(days[days.length - 1]);
			return;
		}
		const idx = days.indexOf(selectedDate);
		const next = idx + direction;
		if (next >= 0 && next < days.length) {
			void onDateChange(days[next]);
		}
	}

	function closeHistory() {
		void onDateChange('');
	}

	// ── Derived: Latest day (Tier 1) ──
	let latestDate = $derived.by(() => agg?.days[agg.days.length - 1] ?? '');
	let latestDayStats = $derived.by(() => latestInsights?.day_stats ?? null);
	let latestRecovery = $derived.by(() => latestInsights?.recovery ?? null);

	let latestStats = $derived.by(() => {
		const pw = agg?.period_windows?.[PERIOD_KEY_MAP[trendRange]];
		if (!pw) return null;
		const hr = pw;
		return { overallAvg: hr.avg, typicalLow: hr.typical_low, typicalHigh: hr.typical_high, avgResting: hr.avg_resting };
	});

	let latestZoneBreakdown = $derived(buildZoneBreakdown(latestInsights));

	// ── Derived: Historical day (Tier 2) ──
	let historicalDayStats = $derived.by(() => historicalInsights?.day_stats ?? null);
	let historicalRecovery = $derived.by(() => historicalInsights?.recovery ?? null);

	let historicalZoneBreakdown = $derived(buildZoneBreakdown(historicalInsights));

	// Map recovery status → color for the day strip
	let dayRecoveryMap = $derived.by(() => {
		if (!agg) return new Map<string, string>();
		const map = new Map<string, string>();
		const avgResting = agg.period_windows?.[PERIOD_KEY_MAP[trendRange]]?.avg_resting;
		if (avgResting == null) return map;
		for (const d of agg.daily) {
			const rhr = d.heart_rate.resting;
			if (rhr == null) { map.set(d.date, '#3a4a5a'); continue; }
			const delta = rhr - avgResting;
			if (delta > 5) map.set(d.date, COLORS.heartRate);
			else if (delta > 2) map.set(d.date, COLORS.stress);
			else map.set(d.date, COLORS.heartRateResting);
		}
		return map;
	});

	let selectedIndex = $derived.by(() => {
		if (!agg || !selectedDate) return -1;
		return agg.days.indexOf(selectedDate);
	});
	let canPrev = $derived(selectedIndex > 0);
	let canNext = $derived.by(() => selectedIndex >= 0 && agg != null && selectedIndex < agg.days.length - 1);

	// ── Helpers ──
	const ZONE_COLORS: Record<string, string> = {
		Rest: '#4A6FA5', Light: '#4CAF82', Moderate: '#D4944C', Vigorous: '#E85D4A'
	};

	function recoveryColor(status: string | null | undefined): string {
		if (status === 'high' || status === 'elevated') return COLORS.heartRate;
		if (status === 'low' || status === 'normal') return COLORS.heartRateResting;
		return '#8a9baa';
	}

	// ── ISO week label formatting ──
	function isoWeekToMonday(isoWeek: string): Date | null {
		const m = isoWeek.match(/^(\d{4})-W(\d{2})$/);
		if (!m) return null;
		const year = parseInt(m[1]), week = parseInt(m[2]);
		const jan4 = new Date(year, 0, 4);
		const dow = (jan4.getDay() + 6) % 7; // Mon=0
		const weekStart = new Date(jan4);
		weekStart.setDate(jan4.getDate() - dow + (week - 1) * 7);
		return weekStart;
	}

	function fmtWeekLabel(isoWeek: string): string {
		const d = isoWeekToMonday(isoWeek);
		if (!d) return isoWeek;
		return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
	}

	// ── Shared chart config ──
	const hrTooltip = chartTooltip(withAlpha(COLORS.heartRate, '60'));
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
		tooltip: hrTooltip
	} as const;

	const ZONE_ANNOTATIONS = {
		restZone: { type: 'box' as const, yMin: 0, yMax: 60, backgroundColor: 'rgba(74,111,165,0.06)', borderWidth: 0, adjustScaleRange: false },
		lightZone: { type: 'box' as const, yMin: 60, yMax: 100, backgroundColor: 'rgba(76,175,130,0.05)', borderWidth: 0, adjustScaleRange: false },
		modZone: { type: 'box' as const, yMin: 100, yMax: 140, backgroundColor: 'rgba(212,148,76,0.05)', borderWidth: 0, adjustScaleRange: false },
		vigZone: { type: 'box' as const, yMin: 140, yMax: 220, backgroundColor: 'rgba(232,93,74,0.05)', borderWidth: 0, adjustScaleRange: false }
	};

	const intradayScales = {
		x: {
			type: 'time' as const,
			time: { unit: 'hour' as const, displayFormats: { hour: 'HH:mm' } },
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
	} as const;

	function buildIntradayConfig(intraday: HeartRateRawData, resting: number | null | undefined): ChartConfiguration<'line'> {
		const datasets: ChartConfiguration<'line'>['data']['datasets'] = [
			{
				label: 'Heart Rate',
				data: intraday.heart_rate.map((d) => d.value),
				borderColor: COLORS.heartRate,
				borderWidth: 1.5,
				pointRadius: 0,
				tension: 0.2,
				fill: false
			}
		];
		if (resting != null) {
			datasets.push({
				label: 'Resting HR',
				data: intraday.heart_rate.map(() => resting),
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
			data: { labels: intraday.heart_rate.map((d) => d.timestamp), datasets },
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: datasets.length > 1, labels: { boxWidth: 12, font: { size: 11 }, color: '#8a9baa' } },
					tooltip: hrTooltip,
					annotation: { annotations: ZONE_ANNOTATIONS }
				},
				scales: intradayScales
			}
		};
	}

	function buildDistributionSidebarConfig(distribution: HRDistribution): ChartConfiguration<'bar'> {
		return {
			type: 'bar' as const,
			data: {
				labels: distribution.bins.map((b) => `${b.bin_start}–${b.bin_end}`),
				datasets: [{
					label: 'Readings',
					data: distribution.bins.map((b) => b.count),
					backgroundColor: withAlpha(COLORS.heartRate, '50'),
					borderColor: COLORS.heartRate,
					borderWidth: 1,
					borderRadius: 2
				}]
			},
			options: {
				indexAxis: 'y' as const,
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: false },
					tooltip: hrTooltip
				},
				scales: {
					x: { display: false, beginAtZero: true, grid: { display: false }, border: { display: false } },
					y: { ticks: { font: { size: 9 }, ...DARK_TICK }, grid: { display: false }, border: { display: false } }
				}
			}
		};
	}

	function buildZoneBreakdown(insights: HeartRateInsights | null) {
		if (!insights || insights.zones.length === 0) return null;
		return insights.zones.map((z) => ({
			label: z.label,
			color: ZONE_COLORS[z.label] ?? '#6b7d8e',
			pct: z.pct,
			minutes: z.minutes
		}));
	}

	function handleTrendClick(_event: unknown, elements: { index: number }[], chart: { data: { labels?: unknown[] } }) {
		const active = elements[0];
		if (!active) return;
		const label = chart.data.labels?.[active.index];
		if (typeof label !== 'string') return;
		if (label === selectedDate) {
			closeHistory();
		} else {
			void onDateChange(label);
		}
	}

	// ── Chart: Intraday (latest & historical) ──
	let latestIntradayConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!latestIntraday || latestIntraday.heart_rate.length === 0) return null;
		return buildIntradayConfig(latestIntraday, latestDayStats?.resting);
	});

	let historicalIntradayConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!historicalIntraday || historicalIntraday.heart_rate.length === 0) return null;
		return buildIntradayConfig(historicalIntraday, historicalDayStats?.resting);
	});

	// ── Chart: Distribution sidebar (latest & historical) ──
	let latestDistributionSidebarConfig = $derived.by<ChartConfiguration<'bar'> | null>(() => {
		if (!latestDistribution || latestDistribution.bins.length === 0) return null;
		return buildDistributionSidebarConfig(latestDistribution);
	});

	let historicalDistributionSidebarConfig = $derived.by<ChartConfiguration<'bar'> | null>(() => {
		if (!historicalDistribution || historicalDistribution.bins.length === 0) return null;
		return buildDistributionSidebarConfig(historicalDistribution);
	});

	// ── Chart: Trend ──
	// ── Chart: Daily Avg HR (with 7-day MA) ──
	let dailyAvgConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!analysis || analysis.daily_avg_trend.length === 0) return null;
		const t = filterByRange(analysis.daily_avg_trend, trendRange);
		const pw = agg?.period_windows?.[PERIOD_KEY_MAP[trendRange]];
		const typicalLow = pw?.typical_low ?? null;
		const typicalHigh = pw?.typical_high ?? null;
		const labels = t.map((p) => p.date);
		const datasets: ChartConfiguration<'line'>['data']['datasets'] = [];

		if (typicalLow != null && typicalHigh != null) {
			datasets.push(
				{
					label: 'Typical Low', data: labels.map(() => typicalLow),
					borderColor: withAlpha(COLORS.heartRate, '40'), borderWidth: 1, borderDash: [3, 3],
					pointRadius: 0, tension: 0, fill: false
				},
				{
					label: 'Typical High', data: labels.map(() => typicalHigh),
					borderColor: withAlpha(COLORS.heartRate, '40'), borderWidth: 1, borderDash: [3, 3],
					pointRadius: 0, tension: 0, fill: '-1', backgroundColor: withAlpha(COLORS.heartRate, '06')
				}
			);
		}
		datasets.push(
			{
				label: 'Daily Avg', data: t.map((p) => p.avg_bpm),
				borderColor: withAlpha(COLORS.heartRate, '50'), borderWidth: 1, pointRadius: 2,
				pointBackgroundColor: COLORS.heartRate, tension: 0, spanGaps: true
			},
			{
				label: '7-Day MA', data: t.map((p) => p.ma7_bpm),
				borderColor: COLORS.heartRate, borderWidth: 2.5,
				pointRadius: 0, tension: 0.3, spanGaps: true
			}
		);
		return {
			type: 'line',
			data: { labels, datasets },
			options: {
				responsive: true, maintainAspectRatio: false,
				interaction: { mode: 'index' as const, intersect: false },
				onClick: handleTrendClick,
				plugins: darkPlugins, scales: darkScales
			}
		};
	});

	// ── Chart: Resting HR (with 7-day MA) ──
	let restingHRConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!analysis || analysis.resting_hr_trend.length === 0) return null;
		const t = filterByRange(analysis.resting_hr_trend, trendRange);
		return {
			type: 'line',
			data: {
				labels: t.map((p) => p.date),
				datasets: [
					{
						label: 'Resting HR', data: t.map((p) => p.resting_bpm),
						borderColor: withAlpha(COLORS.heartRateResting, '50'), borderWidth: 1,
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
				onClick: handleTrendClick,
				plugins: darkPlugins, scales: darkScales
			}
		};
	});

	// ── Chart: Sleeping HR ──
	let sleepingHRConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!analysis || analysis.sleeping_hr_trend.length === 0) return null;
		const trend = filterByRange(analysis.sleeping_hr_trend, trendRange);
		return {
			type: 'line',
			data: {
				labels: trend.map((p) => p.date),
				datasets: [
					{
						label: 'Sleeping HR', data: trend.map((p) => p.avg_sleeping_bpm),
						borderColor: withAlpha(COLORS.sleep, '73'), borderWidth: 1, pointRadius: 2,
						pointBackgroundColor: COLORS.sleep, tension: 0, spanGaps: true
					},
					{
						label: '7-Day MA', data: trend.map((p) => p.ma7_bpm),
						borderColor: COLORS.sleep, borderWidth: 2.5,
						pointRadius: 0, tension: 0.3, spanGaps: true,
						fill: { target: 'origin', above: withAlpha(COLORS.sleep, '1f') }
					}
				]
			},
			options: {
				responsive: true, maintainAspectRatio: false,
				plugins: { legend: { display: true, labels: { color: '#8a9baa', font: { size: 11 }, boxWidth: 12, padding: 16 } }, tooltip: chartTooltip(withAlpha(COLORS.sleep, '99')) },
				scales: darkScales
			}
		};
	});

	// ── Chart: Circadian (polar area) ──
	let circadianConfig = $derived.by<ChartConfiguration<'polarArea'> | null>(() => {
		const profile = analysis?.pattern_windows?.[PERIOD_KEY_MAP[trendRange]]?.circadian_profile ?? [];
		if (profile.length === 0) return null;
		const values = profile.map((p) => p.avg_bpm ?? 0);
		const minBpm = Math.min(...values.filter((v) => v > 0));
		const maxBpm = Math.max(...values);
		const range = maxBpm - minBpm || 1;

		// Color gradient: cool (sleep) → warm (active)
		function bpmColor(bpm: number, alpha: string): string {
			const t = Math.max(0, Math.min(1, (bpm - minBpm) / range));
			// Blue(210°) → Orange(25°) via hue interpolation
			const hue = 210 - t * 185;
			const sat = 55 + t * 20;
			const light = 45 + t * 10;
			return `hsla(${hue}, ${sat}%, ${light}%, ${alpha})`;
		}

		return {
			type: 'polarArea',
			data: {
				labels: profile.map((p) => `${String(p.hour).padStart(2, '0')}:00`),
				datasets: [{
					data: values,
					backgroundColor: values.map((v) => bpmColor(v, '0.7')),
					borderColor: values.map((v) => bpmColor(v, '1')),
					borderWidth: 1
				}]
			},
			options: {
				responsive: true,
				maintainAspectRatio: true,
				startAngle: -90, // Midnight at 12 o'clock (clock-like)
				layout: { padding: 4 },
				plugins: {
					legend: { display: false },
					tooltip: {
						...hrTooltip,
						callbacks: {
							title: (items: { dataIndex: number }[]) => {
								const idx = items[0]?.dataIndex ?? 0;
								return `${String(idx).padStart(2, '0')}:00`;
							},
							label: (ctx: { parsed: { r: number } }) => ` ${ctx.parsed.r} bpm`
						}
					}
				},
				scales: {
					r: {
						beginAtZero: false,
						suggestedMin: Math.max(0, minBpm - 5),
						ticks: { display: false },
						grid: { color: '#ffffff10' },
						pointLabels: { display: false }
					}
				}
			}
		};
	});


	// ── Chart: Weekly Boxplot ──
	let boxplotConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!analysis || analysis.weekly_boxplots.length === 0) return null;
		const cutoff = trendCutoff(trendRange);
		const boxes = cutoff
			? analysis.weekly_boxplots.filter((b) => {
				const d = isoWeekToMonday(b.iso_week);
				return d ? localDateIso(d) >= cutoff : true;
			})
			: analysis.weekly_boxplots;
		const labels = boxes.map((b) => fmtWeekLabel(b.iso_week));
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
				plugins: {
					...darkPlugins,
					tooltip: {
						...darkPlugins.tooltip,
						callbacks: {
							title: (items: { dataIndex: number }[]) => {
								const box = boxes[items[0]?.dataIndex ?? 0];
								const mon = isoWeekToMonday(box.iso_week);
								if (!mon) return box.iso_week;
								const sun = new Date(mon);
								sun.setDate(mon.getDate() + 6);
								const f = (d: Date) => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
								return `${f(mon)} – ${f(sun)}`;
							},
							afterBody: (items: { dataIndex: number }[]) => {
								const n = boxes[items[0]?.dataIndex ?? 0]?.day_count ?? 0;
								return [`${n} day${n !== 1 ? 's' : ''} of data`];
							}
						}
					}
				},
				scales: {
					x: { ticks: { maxRotation: 45, font: { size: 10 }, color: '#6b7d8e' }, grid: { color: '#ffffff08' }, border: { color: '#ffffff10' } },
					y: { beginAtZero: false, title: { display: true, text: 'Resting bpm', color: '#6b7d8e' }, ticks: { color: '#6b7d8e' }, grid: { color: '#ffffff06' }, border: { color: '#ffffff10' } }
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

	<!-- ════════════════════════════════════════════════════ -->
	<!-- TIER 1: TODAY                                        -->
	<!-- ════════════════════════════════════════════════════ -->

	<div class="section-header">
		<span class="section-label">Today</span>
		<span class="section-date">{latestDate}</span>
	</div>

	<!-- Stat bar — always latest day -->
	<div class="stat-bar">
		<div class="stat-item">
			<span class="stat-label">Resting HR</span>
			<span class="stat-value" style="color: #4CAF82;">
				{fmt(latestDayStats?.resting ?? latestStats?.avgResting)}
			</span>
			<span class="stat-unit">bpm</span>
			{#if latestRecovery?.delta_from_baseline != null}
				<span class="stat-delta" style="color: {recoveryColor(latestRecovery?.status)};">
					{fmtSigned(latestRecovery.delta_from_baseline)} vs {fmt(latestRecovery.baseline_resting_7d)} avg
				</span>
			{:else if latestDayStats?.resting == null && latestStats?.avgResting != null}
				<span class="stat-delta" style="color: #6b7d8e;">period avg</span>
			{/if}
		</div>
		<div class="stat-item">
			<span class="stat-label">Recovery</span>
			<span class="recovery-pill" style="background: {recoveryColor(latestRecovery?.status)}20; color: {recoveryColor(latestRecovery?.status)}; border-color: {recoveryColor(latestRecovery?.status)}40;">
				{latestRecovery?.status ? latestRecovery.status.toUpperCase() : '-'}
			</span>
		</div>
		<div class="stat-item">
			<span class="stat-label">Daily Avg</span>
			<span class="stat-value" style="color: #E85D4A;">
				{fmt(latestDayStats?.avg ?? latestStats?.overallAvg)}
			</span>
			<span class="stat-unit">bpm</span>
			{#if latestStats?.overallAvg != null}
				<span class="stat-delta" style="color: #6b7d8e;">
					vs {fmt(latestStats.overallAvg)} avg
				</span>
			{/if}
		</div>
		<div class="stat-item">
			{#if latestDayStats?.min != null && latestDayStats?.max != null}
				<span class="stat-label">Today's Range</span>
				<span class="stat-value" style="color: #c8d6e0;">
					{fmt(latestDayStats.min)}–{fmt(latestDayStats.max)}
				</span>
				<span class="stat-unit">bpm</span>
				{#if latestStats?.typicalLow != null && latestStats?.typicalHigh != null}
					<span class="stat-delta" style="color: #6b7d8e;">
						typical {fmt(latestStats.typicalLow)}–{fmt(latestStats.typicalHigh)}
					</span>
				{/if}
			{:else}
				<span class="stat-label">Typical Range</span>
				<span class="stat-value" style="color: #c8d6e0;">
					{fmt(latestStats?.typicalLow)}–{fmt(latestStats?.typicalHigh)}
				</span>
				<span class="stat-unit">bpm</span>
			{/if}
		</div>
	</div>

	<!-- Insight line — latest day -->
	{#if latestInsights && latestInsights.insights.length > 0}
		{@const topInsight = latestInsights.insights[0]}
		<div class="insight-line">
			<span class="insight-dot" style="background: {insightLevelColor(topInsight.level)};"></span>
			<span class="insight-level" style="color: {insightLevelColor(topInsight.level)};">{topInsight.level.toUpperCase()}</span>
			<span class="insight-text">{topInsight.title}</span>
			<span class="insight-detail">{topInsight.detail}</span>
		</div>
	{/if}

	<!-- Intraday chart + distribution sidebar — latest day -->
	{#if latestIntradayConfig}
		<div class="card">
			<div class="card-header-row">
				<h2 class="card-title">Intraday Heart Rate</h2>
				{#if latestZoneBreakdown}
					<div class="zone-inline">
						<div class="zone-inline-top">
							<span class="zone-inline-label">HR Zones</span>
							<div class="zone-inline-bar">
								{#each latestZoneBreakdown as zone}
									{#if zone.pct > 0}
										<div
											style="width: {zone.pct}%; background: {zone.color};"
											title="{zone.label}: {zone.pct}%"
										></div>
									{/if}
								{/each}
							</div>
						</div>
						<div class="zone-inline-legend">
							{#each latestZoneBreakdown as zone}
								{#if zone.pct > 0}
									<span class="zone-inline-item" title="{zone.label}: {zone.pct}%">
										<i class="legend-dot" style="background: {zone.color};"></i>
										{zone.label} {zone.pct}%
									</span>
								{/if}
							{/each}
						</div>
					</div>
				{/if}
			</div>
			<div class="intraday-with-distribution">
				<div class="intraday-chart-area">
					<LineChart config={latestIntradayConfig} height={280} />
				</div>
				{#if latestDistributionSidebarConfig}
					<div class="distribution-sidebar">
						<BarChart config={latestDistributionSidebarConfig} height={280} />
					</div>
				{/if}
			</div>
			<p class="card-footnote">{latestIntraday?.heart_rate.length ?? 0} readings</p>
		</div>
	{/if}

	<!-- ════════════════════════════════════════════════════ -->
	<!-- TIER 2: HISTORY BAR + EXPANDABLE DETAIL              -->
	<!-- ════════════════════════════════════════════════════ -->

	<div class="section-header tier2-header">
		<span class="section-label">History</span>
		<span class="section-sublabel">Click a day to explore</span>
	</div>

	<!-- Day selector strip -->
	<div class="day-nav">
		<div class="day-nav-controls">
			<button class="nav-arrow" disabled={!canPrev} onclick={() => navigateDay(-1)}>←</button>
			<button class="day-label" onclick={() => closeHistory()}>
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

	<!-- Expandable day detail panel -->
	{#if historyOpen && selectedDate}
		<div class="history-detail" transition:slide={{ duration: 300 }}>
			<div class="history-detail-header">
				<div class="history-detail-title">
					<span class="history-date">{selectedDate}</span>
					{#if historicalDayStats?.resting != null && latestDayStats?.resting != null}
						<span class="history-comparison">
							Resting: <strong>{fmt(historicalDayStats.resting)}</strong> bpm
							<span class="comparison-vs">(today: {fmt(latestDayStats.resting)})</span>
						</span>
					{/if}
				</div>
				<button class="close-btn" onclick={closeHistory} title="Close">✕</button>
			</div>

			{#if historicalIntradayConfig}
				<div class="history-section">
					<div class="card-header-row">
						<h3 class="history-section-title" style="margin-bottom: 0;">Intraday Heart Rate</h3>
						{#if historicalZoneBreakdown}
							<div class="zone-inline">
								<div class="zone-inline-top">
									<span class="zone-inline-label">HR Zones</span>
									<div class="zone-inline-bar">
										{#each historicalZoneBreakdown as zone}
											{#if zone.pct > 0}
												<div
													style="width: {zone.pct}%; background: {zone.color};"
													title="{zone.label}: {zone.pct}%"
												></div>
											{/if}
										{/each}
									</div>
								</div>
								<div class="zone-inline-legend">
									{#each historicalZoneBreakdown as zone}
										{#if zone.pct > 0}
											<span class="zone-inline-item" title="{zone.label}: {zone.pct}%">
												<i class="legend-dot" style="background: {zone.color};"></i>
												{zone.label} {zone.pct}%
											</span>
										{/if}
									{/each}
								</div>
							</div>
						{/if}
					</div>
					<div class="intraday-with-distribution">
						<div class="intraday-chart-area">
							<LineChart config={historicalIntradayConfig} height={240} />
						</div>
						{#if historicalDistributionSidebarConfig}
							<div class="distribution-sidebar">
								<BarChart config={historicalDistributionSidebarConfig} height={240} />
							</div>
						{/if}
					</div>
					<p class="card-footnote">{historicalIntraday?.heart_rate.length ?? 0} readings</p>
				</div>
			{:else if !historicalIntraday}
				<div class="text-sm text-[#5e7282] py-4">Loading intraday data...</div>
			{/if}

			{#if historicalInsights && historicalInsights.insights.length > 0}
				<div class="history-section">
					<h3 class="history-section-title">Recovery Insights</h3>
					<div class="insights-list">
						{#each historicalInsights.insights as item}
							<div class="insight-card" style="border-left-color: {insightLevelColor(item.level)};">
								<div class="insight-card-level" style="color: {insightLevelColor(item.level)};">{item.level}</div>
								<div class="insight-card-title">{item.title}</div>
								<div class="insight-card-detail">{item.detail}</div>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	{/if}

	<!-- ════════════════════════════════════════════════════ -->
	<!-- TIER 3: TRENDS                                       -->
	<!-- ════════════════════════════════════════════════════ -->

	<div class="section-header tier3-header">
		<span class="section-label">Trends</span>
		<TrendRangePicker bind:value={trendRange} />
	</div>

	<!-- Heart Rate Trends — side by side -->
	<div class="two-col-row">
		{#if dailyAvgConfig}
			<div class="card two-col-item">
				<h2 class="card-title">Daily Avg HR — Click to Explore <span class="info-hint" data-tip="Click any point to explore that day. Thick line = 7-day moving average. Shaded band = your typical range.">ⓘ</span></h2>
				<LineChart config={dailyAvgConfig} height={260} />
			</div>
		{/if}

		{#if restingHRConfig}
			<div class="card two-col-item">
				<h2 class="card-title">Resting HR</h2>
				<LineChart config={restingHRConfig} height={260} />
			</div>
		{/if}
	</div>

	<!-- Sleep & Recovery -->
	<div class="section-subheader">
		<span class="section-sublabel">Sleep & Recovery</span>
	</div>

	<div class="two-col-row">
		{#if sleepingHRConfig}
			<div class="card two-col-item">
				<h2 class="card-title">Sleeping HR Trend <span class="info-hint" data-tip="Average HR during sleep stages (light, deep, REM) — excludes awake time. Lower is generally better.">ⓘ</span></h2>
				<LineChart config={sleepingHRConfig} height={280} />
				<p class="card-footnote">Average HR during light/deep/REM sleep stages (excludes awake)</p>
			</div>
		{/if}

		{#if circadianConfig}
			<div class="card two-col-item">
				<h2 class="card-title">Circadian HR Profile <span class="info-hint" data-tip="Average HR by hour of day. Midnight at top, clockwise. Blue = resting hours, warm = active hours.">ⓘ</span></h2>
				<PolarAreaChart config={circadianConfig} height={320} />
				<p class="card-footnote">Avg HR by hour · blue = rest · warm = active</p>
			</div>
		{/if}
	</div>

	<!-- Analysis -->
	<div class="section-subheader">
		<span class="section-sublabel">Analysis</span>
	</div>

	{#if boxplotConfig}
		<div class="card">
			<h2 class="card-title">Resting HR — Weekly Spread <span class="info-hint" data-tip="How much your resting HR varies within each week. Narrow band = consistent. Wide band = variable.">ⓘ</span></h2>
			<LineChart config={boxplotConfig} height={260} />
			<p class="card-footnote">Shaded band = middle 50% of days · dashes = extremes · bold line = median</p>
		</div>
	{/if}

	<MetricDefinition title="How to Read This Dashboard">
		<div class="reading-guide">
			<div class="guide-section">
				<strong class="guide-heading">Today (top)</strong>
				<p>Your snapshot right now. Resting HR, Recovery, and Daily Avg are today's actual values. The intraday chart shows your full day — the dashed line is your resting HR baseline.</p>
			</div>
			<div class="guide-section">
				<strong class="guide-heading">History strip</strong>
				<p>Green = normal · Orange = elevated · Red = high. Each block is one day, colored by how resting HR compared to your 7-day average. Click any block to drill into that day.</p>
			</div>
			<div class="guide-section">
				<strong class="guide-heading">Trend charts — the bold line is the signal</strong>
				<p>Raw daily values are noisy. The thick 7-day moving average reveals the real trend — watch it for multi-week drift up or down. Click any point to jump to that day's detail.</p>
			</div>
			<div class="guide-section">
				<strong class="guide-heading">Sleep & Recovery — your heart's overnight report card</strong>
				<p>Sleeping HR measures your true autonomic state during actual sleep stages (not awake time). The clock chart shows when your heart works hardest vs. rests — look for deep blue between 2–5 AM.</p>
			</div>
			<div class="guide-section">
				<strong class="guide-heading">Weekly spread — consistency is the goal</strong>
				<p>A narrow, stable band means your resting HR baseline is consistent. A widening band or rising median may signal accumulated fatigue or illness. Weeks with fewer days of data (shown in tooltips) are less reliable.</p>
			</div>
		</div>
	</MetricDefinition>
{/if}

<style>
	/* ── Section Headers ── */
	.section-header {
		display: flex;
		align-items: baseline;
		gap: 10px;
		padding-bottom: 10px;
		margin-bottom: 14px;
		border-bottom: 1px solid rgba(255,255,255,0.06);
	}
	.tier2-header {
		margin-top: 28px;
	}
	.tier3-header {
		margin-top: 28px;
	}
	.section-label {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 2px;
		color: #6b7d8e;
		font-weight: 600;
	}
	.section-date {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #4a5c6a;
	}
	.section-sublabel {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		color: #4a5c6a;
		letter-spacing: 1px;
	}
	.section-subheader {
		padding-bottom: 8px;
		margin-bottom: 12px;
		margin-top: 20px;
		border-bottom: 1px solid rgba(255,255,255,0.04);
	}

	/* ── Sleep & Recovery side-by-side ── */
	.two-col-row {
		display: flex;
		gap: 16px;
	}
	.two-col-item {
		flex: 1;
		min-width: 0;
	}

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

	/* ── History Detail Panel ── */
	.history-detail {
		background: rgba(255,255,255,0.025);
		border: 1px solid rgba(232,93,74,0.15);
		border-left: 3px solid rgba(232,93,74,0.4);
		border-radius: 10px;
		padding: 20px;
		margin-bottom: 14px;
	}
	.history-detail-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 16px;
	}
	.history-detail-title {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.history-date {
		font-family: 'DM Mono', monospace;
		font-size: 16px;
		font-weight: 600;
		color: #e8f0f5;
		letter-spacing: 0.5px;
	}
	.history-comparison {
		font-size: 12px;
		color: #8a9baa;
	}
	.history-comparison strong {
		color: #c8d6e0;
	}
	.comparison-vs {
		color: #5e7282;
	}
	.close-btn {
		width: 28px;
		height: 28px;
		border-radius: 6px;
		border: 1px solid rgba(255,255,255,0.1);
		background: rgba(255,255,255,0.03);
		color: #6b7d8e;
		cursor: pointer;
		font-size: 14px;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.15s;
		flex-shrink: 0;
	}
	.close-btn:hover { background: rgba(255,255,255,0.08); color: #c8d6e0; }

	.history-section {
		margin-top: 16px;
		padding-top: 16px;
		border-top: 1px solid rgba(255,255,255,0.04);
	}
	.history-section:first-of-type {
		margin-top: 0;
		padding-top: 0;
		border-top: none;
	}
	.history-section-title {
		font-size: 11px;
		font-weight: 600;
		color: #6b7d8e;
		text-transform: uppercase;
		letter-spacing: 1px;
		margin-bottom: 10px;
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

	/* ── Info hint icon with CSS tooltip ── */
	.info-hint {
		font-size: 11px;
		color: #4a5c6a;
		cursor: help;
		margin-left: 4px;
		vertical-align: middle;
		user-select: none;
		position: relative;
	}
	.info-hint:hover {
		color: #8a9baa;
	}
	.info-hint:hover::after {
		content: attr(data-tip);
		position: absolute;
		left: 50%;
		top: calc(100% + 6px);
		transform: translateX(-50%);
		background: rgba(13, 21, 32, 0.95);
		color: #c8d6e0;
		font-size: 11px;
		font-weight: 400;
		letter-spacing: 0;
		text-transform: none;
		line-height: 1.4;
		padding: 8px 12px;
		border-radius: 6px;
		border: 1px solid rgba(255, 255, 255, 0.12);
		white-space: normal;
		width: max-content;
		max-width: 280px;
		z-index: 50;
		pointer-events: none;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
	}

	/* ── Dashboard reading guide ── */
	.reading-guide {
		display: flex;
		flex-direction: column;
		gap: 12px;
		padding-top: 4px;
	}
	.guide-section {
		display: flex;
		flex-direction: column;
		gap: 3px;
	}
	.guide-heading {
		color: #c8d6e0;
		font-size: 12px;
		font-weight: 600;
		letter-spacing: 0.3px;
	}

	/* ── Intraday + Distribution sidebar ── */
	.intraday-with-distribution {
		display: flex;
		gap: 12px;
		align-items: stretch;
	}
	.intraday-chart-area {
		flex: 1;
		min-width: 0;
	}
	.distribution-sidebar {
		width: 28%;
		min-width: 180px;
		max-width: 280px;
		flex-shrink: 0;
	}

	/* ── Inline zone bar (card header) ── */
	.card-header-row {
		display: flex;
		align-items: flex-start;
		gap: 16px;
		margin-bottom: 14px;
	}
	.card-header-row .card-title,
	.card-header-row .history-section-title {
		margin-bottom: 0;
		flex-shrink: 0;
	}
	.zone-inline {
		display: flex;
		flex-direction: column;
		gap: 5px;
		margin-left: auto;
		min-width: 0;
		overflow: hidden;
	}
	.zone-inline-top {
		display: flex;
		align-items: center;
		gap: 10px;
	}
	.zone-inline-label {
		font-size: 10px;
		font-weight: 600;
		color: #5e7282;
		text-transform: uppercase;
		letter-spacing: 1px;
		white-space: nowrap;
		flex-shrink: 0;
	}
	.zone-inline-bar {
		display: flex;
		flex: 1;
		min-width: 80px;
		height: 10px;
		border-radius: 3px;
		overflow: hidden;
	}
	.zone-inline-bar > div {
		transition: opacity 0.15s;
	}
	.zone-inline-bar > div:hover {
		opacity: 0.8;
	}
	.zone-inline-legend {
		display: flex;
		gap: 10px;
		flex-wrap: wrap;
	}
	.zone-inline-item {
		font-size: 11px;
		color: #8a9baa;
		display: flex;
		align-items: center;
		gap: 4px;
		white-space: nowrap;
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
		.day-nav { flex-direction: column; align-items: stretch; }
		.intraday-with-distribution { flex-direction: column; }
		.distribution-sidebar { width: 100%; max-width: none; min-width: 0; }
		.zone-inline-legend { display: none; }
		.two-col-row { flex-direction: column; }
	}
</style>
