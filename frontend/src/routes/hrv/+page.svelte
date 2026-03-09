<script lang="ts">
	import { onMount } from 'svelte';
	import { slide } from 'svelte/transition';
	import {
		api,
		type DailyAggregates,
		type HrvInsights,
		type HrvAnalysis
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
	let analysis: HrvAnalysis | null = $state(null);
	let loading = $state(true);
	let error: string | null = $state(null);

	// Latest day (Tier 1 — always the most recent)
	let latestInsights: HrvInsights | null = $state(null);

	// Historical day (Tier 2 — selected via strip)
	let selectedDate = $state('');
	let historyOpen = $state(false);
	let historicalInsights: HrvInsights | null = $state(null);
	let dateRequestId = 0;

	// ── Data fetching ──
	async function fetchData() {
		const [nextAgg, nextAnalysis] = await Promise.all([
			api.getDailyAggregates(),
			api.getHrvAnalysis()
		]);
		agg = nextAgg;
		analysis = nextAnalysis;

		// Always fetch latest day data for Tier 1
		if (nextAgg.days.length > 0) {
			const latest = nextAgg.days[nextAgg.days.length - 1];
			const ins = await api.getHrvInsights(latest);
			latestInsights = ins;
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
			return;
		}
		selectedDate = date;
		historyOpen = true;
		historicalInsights = null;
		const requestId = ++dateRequestId;
		try {
			const nextInsights = await api.getHrvInsights(date);
			if (requestId !== dateRequestId) return;
			historicalInsights = nextInsights;
		} catch (e: unknown) {
			if (requestId !== dateRequestId) return;
			error = e instanceof Error ? e.message : String(e);
		}
	}

	function closeHistory() {
		selectedDate = '';
		historyOpen = false;
		historicalInsights = null;
	}

	// ── Computed: Latest day ──
	let latestDate = $derived.by(() => {
		if (!agg) return '';
		return agg.days[agg.days.length - 1] ?? '';
	});
	let latestDayStats = $derived.by(() => latestInsights?.day_stats ?? null);
	let latestRecovery = $derived.by(() => latestInsights?.recovery ?? null);
	let latestStreak = $derived.by(() => latestInsights?.streak ?? null);
	let latestQuality = $derived.by(() => latestInsights?.quality ?? null);

	// ── Computed: History strip colors ──
	const HRV_STATUS_COLORS: Record<string, string> = {
		'Balanced': '#4CAF82',
		'Low': '#E85D4A',
		'Unbalanced': '#D4944C',
		'High': '#5BB5A6'
	};

	let dayStatusMap = $derived.by(() => {
		const map = new Map<string, string>();
		if (!agg) return map;
		for (const d of agg.daily) {
			const status = d.hrv.status;
			const key = status ? status.charAt(0).toUpperCase() + status.slice(1).toLowerCase() : null;
			map.set(d.date, key ? (HRV_STATUS_COLORS[key] ?? '#3a4a5a') : '#3a4a5a');
		}
		return map;
	});

	// ── Navigation ──
	let selectedIndex = $derived.by(() => agg ? agg.days.indexOf(selectedDate) : -1);
	let canPrev = $derived(selectedIndex > 0);
	let canNext = $derived.by(() => agg != null && selectedIndex >= 0 && selectedIndex < agg.days.length - 1);

	function navigateDay(delta: number) {
		if (!agg) return;
		const newIdx = selectedIndex + delta;
		if (newIdx >= 0 && newIdx < agg.days.length) {
			void onDateChange(agg.days[newIdx]);
		}
	}

	// ── Computed: Historical day ──
	let historicalDayStats = $derived.by(() => historicalInsights?.day_stats ?? null);
	let historicalRecovery = $derived.by(() => historicalInsights?.recovery ?? null);
	let historicalTrajectory = $derived.by(() => historicalInsights?.trajectory ?? null);
	let historicalStatusMix = $derived.by(() => historicalInsights?.status_mix ?? []);

	// ── Latest overnight intraday chart ──
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
					tooltip: chartTooltip(withAlpha(COLORS.hrv, '60'))
				},
				scales: {
					x: {
						type: 'time',
						time: {
							unit: 'hour',
							displayFormats: { hour: 'HH:mm' },
							parser: (v: string) => {
								// Parse as UTC to avoid browser DST reinterpretation
								const [y, mo, d, h, mi, s] = v.match(/\d+/g)!.map(Number);
								return Date.UTC(y, mo - 1, d, h, mi, s);
							}
						},
						ticks: {
							font: { size: 10 },
							...DARK_TICK,
							callback: (val: number) => {
								const dt = new Date(val);
								return `${String(dt.getUTCHours()).padStart(2, '0')}:${String(dt.getUTCMinutes()).padStart(2, '0')}`;
							}
						},
						grid: DARK_GRID,
						border: DARK_BORDER
					},
					y: {
						beginAtZero: false,
						title: { display: true, text: 'ms', ...DARK_TICK },
						ticks: DARK_TICK,
						grid: DARK_GRID_Y,
						border: DARK_BORDER
					}
				}
			}
		};
	}

	let latestIntradaySegment = $derived.by(
		() => latestInsights?.intraday_segments.find((s) => s.key === 'all') ?? null
	);
	let latestIntradayConfig = $derived.by(() => makeIntradayConfig(latestIntradaySegment, COLORS.hrv));

	let historicalIntradaySegment = $derived.by(
		() => historicalInsights?.intraday_segments.find((s) => s.key === 'all') ?? null
	);
	let historicalIntradayConfig = $derived.by(() => makeIntradayConfig(historicalIntradaySegment, COLORS.hrv));

	// ── Trend time-window ──
	type TrendRange = '1M' | '3M' | '6M' | 'All';
	const TREND_RANGES: TrendRange[] = ['1M', '3M', '6M', 'All'];
	let trendRange: TrendRange = $state('3M');

	function trendCutoff(range: TrendRange): string | null {
		if (range === 'All') return null;
		const d = new Date();
		const months = range === '1M' ? 1 : range === '3M' ? 3 : 6;
		d.setMonth(d.getMonth() - months);
		return d.toISOString().slice(0, 10);
	}

	// ── Trend chart helpers ──
	const darkPlugins = {
		legend: { labels: { boxWidth: 12, font: { size: 11 }, color: '#8a9baa' } },
		tooltip: chartTooltip(withAlpha(COLORS.hrv, '60'))
	};

	function handleTrendClick(_event: unknown, elements: { index: number }[], chart: { data: { labels?: unknown[] } }) {
		const active = elements[0];
		if (!active) return;
		const label = chart.data.labels?.[active.index];
		if (typeof label !== 'string' || label === selectedDate) return;
		void onDateChange(label);
	}

	// ── ISO week helpers (for boxplot labels) ──
	function isoWeekToMonday(isoWeek: string): Date | null {
		const m = isoWeek.match(/^(\d{4})-W(\d{2})$/);
		if (!m) return null;
		const year = parseInt(m[1]), week = parseInt(m[2]);
		const jan4 = new Date(year, 0, 4);
		const dow = (jan4.getDay() + 6) % 7;
		const weekStart = new Date(jan4);
		weekStart.setDate(jan4.getDate() - dow + (week - 1) * 7);
		return weekStart;
	}

	function fmtWeekLabel(isoWeek: string): string {
		const d = isoWeekToMonday(isoWeek);
		if (!d) return isoWeek;
		return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
	}

	// ── Trend chart: Nightly HRV with 7-day MA ──
	let nightlyTrendConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!analysis || analysis.nightly_trend.length === 0) return null;
		const cutoff = trendCutoff(trendRange);
		const t = cutoff ? analysis.nightly_trend.filter((p) => p.date >= cutoff) : analysis.nightly_trend;
		const lowBand = latestInsights?.trend_band.nightly_typical_low ?? null;
		const highBand = latestInsights?.trend_band.nightly_typical_high ?? null;
		const baseline30d = latestInsights?.long_baseline?.baseline_30d ?? null;
		const baselineBands = latestInsights?.baseline_bands ?? null;

		const labels = t.map((p) => p.date);
		const datasets: ChartConfiguration<'line'>['data']['datasets'] = [];

		// Typical low/high band
		if (lowBand != null && highBand != null) {
			datasets.push(
				{
					label: 'Typical Low',
					data: labels.map(() => lowBand),
					borderColor: withAlpha(COLORS.hrvWeekly, '40'),
					borderWidth: 1,
					borderDash: [3, 3],
					pointRadius: 0,
					tension: 0,
					fill: false
				},
				{
					label: 'Typical High',
					data: labels.map(() => highBand),
					borderColor: withAlpha(COLORS.hrvWeekly, '40'),
					borderWidth: 1,
					borderDash: [3, 3],
					pointRadius: 0,
					tension: 0,
					fill: '-1',
					backgroundColor: withAlpha(COLORS.hrvWeekly, '14')
				}
			);
		}

		// 30-day baseline reference
		if (baseline30d != null) {
			datasets.push({
				label: '30-Day Baseline',
				data: labels.map(() => baseline30d),
				borderColor: COLORS.baseline,
				borderWidth: 1.5,
				borderDash: [8, 4],
				pointRadius: 0,
				tension: 0,
				fill: false
			});
		}

		// Raw nightly (light) + 7-day MA (bold)
		datasets.push(
			{
				label: 'Nightly HRV',
				data: t.map((p) => p.nightly_avg),
				borderColor: withAlpha(COLORS.hrv, '50'),
				borderWidth: 1,
				pointRadius: 2,
				pointBackgroundColor: withAlpha(COLORS.hrv, '50'),
				tension: 0.3,
				spanGaps: true
			},
			{
				label: '7-Day MA',
				data: t.map((p) => p.ma7),
				borderColor: COLORS.hrv,
				borderWidth: 2.5,
				pointRadius: 0,
				tension: 0.3,
				spanGaps: true
			}
		);

		// Zone annotations
		const annotationPlugin = baselineBands
			? {
					annotations: {
						lowZone: {
							type: 'box' as const,
							yMin: 0,
							yMax: baselineBands.baseline_low_upper ?? undefined,
							backgroundColor: withAlpha(COLORS.heartRate, '0F'),
							borderWidth: 0,
							adjustScaleRange: false
						},
						balancedZone: {
							type: 'box' as const,
							yMin: baselineBands.baseline_balanced_lower ?? undefined,
							yMax: baselineBands.baseline_balanced_upper ?? undefined,
							backgroundColor: withAlpha(COLORS.heartRateResting, '0F'),
							borderWidth: 0,
							adjustScaleRange: false
						}
					}
				}
			: undefined;

		return {
			type: 'line',
			data: { labels, datasets },
			options: {
				responsive: true,
				maintainAspectRatio: false,
				interaction: { mode: 'index' as const, intersect: false },
				onClick: (_event: unknown, elements: { index: number }[], chart: { data: { labels?: unknown[] } }) => handleTrendClick(_event, elements, chart),
				plugins: {
					...darkPlugins,
					annotation: annotationPlugin
				},
				scales: {
					x: {
						ticks: { maxRotation: 45, font: { size: 10 }, ...DARK_TICK },
						grid: DARK_GRID,
						border: DARK_BORDER
					},
					y: {
						beginAtZero: false,
						title: { display: true, text: 'ms', ...DARK_TICK },
						ticks: DARK_TICK,
						grid: DARK_GRID_Y,
						border: DARK_BORDER
					}
				}
			}
		};
	});

	// ── Boxplot chart: Weekly HRV spread ──
	let boxplotConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!analysis || analysis.weekly_boxplots.length === 0) return null;
		const cutoff = trendCutoff(trendRange);
		const boxes = cutoff
			? analysis.weekly_boxplots.filter((b) => {
					const mon = isoWeekToMonday(b.iso_week);
					return mon ? mon.toISOString().slice(0, 10) >= cutoff : true;
				})
			: analysis.weekly_boxplots;
		const labels = boxes.map((b) => fmtWeekLabel(b.iso_week));

		return {
			type: 'line',
			data: {
				labels,
				datasets: [
					{
						label: 'Min',
						data: boxes.map((b) => b.min_ms),
						borderColor: withAlpha('#c8d6e0', '30'),
						borderWidth: 1,
						borderDash: [4, 3],
						pointRadius: 0,
						tension: 0.3,
						fill: false
					},
					{
						label: 'Q1',
						data: boxes.map((b) => b.q1_ms),
						borderColor: withAlpha('#c8d6e0', '50'),
						borderWidth: 1,
						pointRadius: 0,
						tension: 0.3,
						fill: false
					},
					{
						label: 'Median',
						data: boxes.map((b) => b.median_ms),
						borderColor: '#c8d6e0',
						borderWidth: 2.5,
						pointRadius: 3,
						pointBackgroundColor: '#c8d6e0',
						tension: 0.3,
						fill: false
					},
					{
						label: 'Q3',
						data: boxes.map((b) => b.q3_ms),
						borderColor: withAlpha('#c8d6e0', '50'),
						borderWidth: 1,
						pointRadius: 0,
						tension: 0.3,
						fill: '-2',
						backgroundColor: withAlpha('#c8d6e0', '12')
					},
					{
						label: 'Max',
						data: boxes.map((b) => b.max_ms),
						borderColor: withAlpha('#c8d6e0', '30'),
						borderWidth: 1,
						borderDash: [4, 3],
						pointRadius: 0,
						tension: 0.3,
						fill: false
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				interaction: { mode: 'index' as const, intersect: false },
				plugins: {
					legend: { display: false },
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
					x: {
						ticks: { maxRotation: 45, font: { size: 10 }, ...DARK_TICK },
						grid: DARK_GRID,
						border: DARK_BORDER
					},
					y: {
						beginAtZero: false,
						title: { display: true, text: 'ms', ...DARK_TICK },
						ticks: DARK_TICK,
						grid: DARK_GRID_Y,
						border: DARK_BORDER
					}
				}
			}
		};
	});

	// ── Pattern window (3M floor: 1M→3M, others pass through) ──
	const PATTERN_KEY_MAP: Record<TrendRange, string> = { '1M': '3M', '3M': '3M', '6M': '6M', 'All': 'All' };
	let patternWindow = $derived.by(() => {
		const key = PATTERN_KEY_MAP[trendRange];
		return analysis?.pattern_windows?.[key] ?? null;
	});

	// ── Distribution chart ──
	let distribution = $derived.by(() => patternWindow?.distribution ?? null);

	let distributionConfig = $derived.by<ChartConfiguration<'bar'> | null>(() => {
		if (!distribution || distribution.bins.length === 0) return null;
		const selectedValue = distribution.selected_value;
		return {
			type: 'bar',
			data: {
				labels: distribution.bins.map((b) => `${b.bin_start}–${b.bin_end}`),
				datasets: [
					{
						label: 'Nights',
						data: distribution.bins.map((b) => b.count),
						backgroundColor: distribution.bins.map((b) =>
							selectedValue != null && selectedValue >= b.bin_start && selectedValue < b.bin_end
								? withAlpha(COLORS.hrv, 'cc')
								: withAlpha(COLORS.hrv, '55')
						),
						borderRadius: 2
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: false },
					tooltip: chartTooltip(withAlpha(COLORS.hrv, '60'))
				},
				scales: {
					x: {
						title: { display: true, text: 'HRV (ms)', ...DARK_TICK },
						ticks: { ...DARK_TICK, font: { size: 10 } },
						grid: DARK_GRID,
						border: DARK_BORDER
					},
					y: {
						beginAtZero: true,
						title: { display: true, text: 'Nights', ...DARK_TICK },
						ticks: { ...DARK_TICK, stepSize: 1 },
						grid: DARK_GRID_Y,
						border: DARK_BORDER
					}
				}
			}
		};
	});

	// ── Day of Week chart ──
	let dayOfWeek = $derived.by(() => patternWindow?.day_of_week ?? []);

	let dayOfWeekConfig = $derived.by<ChartConfiguration<'bar'> | null>(() => {
		if (dayOfWeek.length === 0) return null;
		const validAvgs = dayOfWeek.filter((b) => b.avg_nightly != null).map((b) => b.avg_nightly!);
		const overallAvg = validAvgs.length > 0 ? validAvgs.reduce((a, b) => a + b, 0) / validAvgs.length : null;
		return {
			type: 'bar',
			data: {
				labels: dayOfWeek.map((b) => b.day),
				datasets: [
					{
						label: 'Avg Nightly HRV',
						data: dayOfWeek.map((b) => b.avg_nightly),
						backgroundColor: dayOfWeek.map((b) => {
							if (b.avg_nightly == null || overallAvg == null) return withAlpha(COLORS.hrv, '55');
							if (b.avg_nightly - overallAvg > 5) return withAlpha(COLORS.hrv, 'cc');
							if (b.avg_nightly - overallAvg < -5) return withAlpha(COLORS.hrv, '33');
							return withAlpha(COLORS.hrv, '77');
						}),
						borderRadius: 3
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: false },
					tooltip: chartTooltip(withAlpha(COLORS.hrv, '60'))
				},
				scales: {
					x: {
						ticks: { ...DARK_TICK, font: { size: 11 } },
						grid: DARK_GRID,
						border: DARK_BORDER
					},
					y: {
						beginAtZero: false,
						title: { display: true, text: 'ms', ...DARK_TICK },
						ticks: DARK_TICK,
						grid: DARK_GRID_Y,
						border: DARK_BORDER
					}
				}
			}
		};
	});

	// ── Helper functions ──
	function recoveryColor(status: string | null | undefined): string {
		if (status === 'suppressed' || status === 'below_baseline') return '#E85D4A';
		if (status === 'elevated' || status === 'stable') return '#4CAF82';
		return '#6b7d8e';
	}

	function streakColor(status: string | null | undefined): string {
		if (status === 'Low' || status === 'Unbalanced') return '#E85D4A';
		if (status === 'Balanced' || status === 'High') return '#4CAF82';
		return '#6b7d8e';
	}

	function trajectoryArrow(direction: string | null | undefined): string {
		if (direction === 'rising') return '↑';
		if (direction === 'falling') return '↓';
		return '→';
	}

	function trajectoryColor(direction: string | null | undefined): string {
		if (direction === 'rising') return '#4CAF82';
		if (direction === 'falling') return '#E85D4A';
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

	<!-- ════════════════════════════════════════════════════ -->
	<!-- TIER 1: TODAY                                        -->
	<!-- ════════════════════════════════════════════════════ -->

	<div class="section-header">
		<span class="section-label">Tonight</span>
		<span class="section-date">{latestDate}</span>
	</div>

	<!-- Stat bar — always latest day -->
	<div class="stat-bar">
		<div class="stat-item">
			<span class="stat-label">Nightly HRV</span>
			<span class="stat-value" style="color: {COLORS.hrv};">
				{fmt(latestDayStats?.nightly_avg)}
			</span>
			<span class="stat-unit">ms</span>
			{#if latestRecovery?.delta_nightly_from_baseline != null}
				<span class="stat-delta" style="color: {recoveryColor(latestRecovery?.status)};">
					{fmtSigned(latestRecovery.delta_nightly_from_baseline)} vs {fmt(latestRecovery.baseline_nightly_7d)} avg
				</span>
			{/if}
		</div>
		<div class="stat-item">
			<span class="stat-label">Recovery</span>
			<span class="recovery-pill" style="background: {recoveryColor(latestRecovery?.status)}20; color: {recoveryColor(latestRecovery?.status)}; border-color: {recoveryColor(latestRecovery?.status)}40;">
				{latestRecovery?.status ? latestRecovery.status.replace('_', ' ').toUpperCase() : '-'}
			</span>
		</div>
		<div class="stat-item">
			<span class="stat-label">Weekly Avg</span>
			<span class="stat-value" style="color: {COLORS.hrvWeekly};">
				{fmt(latestDayStats?.weekly_avg)}
			</span>
			<span class="stat-unit">ms</span>
			{#if latestDayStats?.status}
				<span class="stat-delta" style="color: {streakColor(latestDayStats.status)};">
					{latestDayStats.status}
				</span>
			{/if}
		</div>
		<div class="stat-item">
			<span class="stat-label">Streak</span>
			{#if latestStreak}
				<span class="stat-value" style="color: {streakColor(latestStreak.current_status)};">
					{latestStreak.streak_days}d
				</span>
				<span class="stat-delta" style="color: {streakColor(latestStreak.current_status)};">
					{latestStreak.current_status ?? '-'}
				</span>
			{:else}
				<span class="stat-value" style="color: #6b7d8e;">-</span>
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

	<!-- Overnight intraday chart — latest day -->
	{#if latestIntradayConfig}
		<div class="card">
			<h2 class="card-title">Overnight HRV — {latestDate}</h2>
			<LineChart config={latestIntradayConfig} height={260} />
			<p class="card-footnote">
				{latestIntradaySegment?.sample_count ?? 0} readings
				{#if latestQuality}· {fmtTimeWindow(latestQuality.coverage_start, latestQuality.coverage_end)}{/if}
				{#if latestIntradaySegment?.avg != null} · avg {fmt(latestIntradaySegment.avg)} ms{/if}
			</p>
		</div>
	{/if}

	<!-- ════════════════════════════════════════════════════ -->
	<!-- TIER 2: HISTORY STRIP + EXPANDABLE DETAIL            -->
	<!-- ════════════════════════════════════════════════════ -->

	<div class="section-header tier2-header">
		<span class="section-label">History</span>
		<span class="section-sublabel">Click a night to explore</span>
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
						style="background: {dayStatusMap.get(day) ?? '#3a4a5a'};"
						title={day}
						onclick={() => onDateChange(day === selectedDate ? '' : day)}
					></button>
				{/each}
			</div>
			<div class="day-strip-legend">
				<span><i class="legend-dot" style="background:#4CAF82;"></i>Balanced</span>
				<span><i class="legend-dot" style="background:#D4944C;"></i>Unbalanced</span>
				<span><i class="legend-dot" style="background:#E85D4A;"></i>Low</span>
			</div>
		</div>
	</div>

	<!-- Expandable day detail panel -->
	{#if historyOpen && selectedDate}
		<div class="history-detail" transition:slide={{ duration: 300 }}>
			<div class="history-detail-header">
				<div class="history-detail-title">
					<span class="history-date">{selectedDate}</span>
					{#if historicalDayStats?.nightly_avg != null && latestDayStats?.nightly_avg != null}
						<span class="history-comparison">
							Nightly: <strong>{fmt(historicalDayStats.nightly_avg)}</strong> ms
							<span class="comparison-vs">(tonight: {fmt(latestDayStats.nightly_avg)})</span>
						</span>
					{/if}
				</div>
				<button class="close-btn" onclick={closeHistory} title="Close">✕</button>
			</div>

			{#if historicalIntradayConfig}
				<div class="history-section">
					<h3 class="history-section-title">Overnight HRV</h3>
					<LineChart config={historicalIntradayConfig} height={220} />
					<p class="card-footnote">
						{historicalIntradaySegment?.sample_count ?? 0} readings
						{#if historicalIntradaySegment?.avg != null} · avg {fmt(historicalIntradaySegment.avg)} ms{/if}
						{#if historicalIntradaySegment?.stdev != null} · stdev {historicalIntradaySegment.stdev} ms{/if}
					</p>
				</div>
			{:else if !historicalInsights}
				<div class="text-sm text-[#5e7282] py-4">Loading overnight data...</div>
			{/if}

			<!-- Trajectory mini-bar -->
			{#if historicalTrajectory}
				{@const tVals = [historicalTrajectory.early_avg, historicalTrajectory.mid_avg, historicalTrajectory.late_avg]}
				{@const tMax = Math.max(...tVals.filter((v): v is number => v != null))}
				<div class="history-section">
					<h3 class="history-section-title">Overnight Trajectory</h3>
					<div class="trajectory-bar">
						{#each [{ label: 'Early', val: tVals[0] }, { label: 'Mid', val: tVals[1] }, { label: 'Late', val: tVals[2] }] as segment}
							<div class="trajectory-segment">
								<div class="trajectory-fill" style="height: {segment.val != null && tMax > 0 ? (segment.val / tMax) * 100 : 0}%; background: {withAlpha(COLORS.hrv, '60')};"></div>
								<span class="trajectory-val">{fmt(segment.val)}</span>
								<span class="trajectory-label">{segment.label}</span>
							</div>
						{/each}
						<span class="trajectory-direction" style="color: {trajectoryColor(historicalTrajectory.direction)};">
							{trajectoryArrow(historicalTrajectory.direction)} {historicalTrajectory.direction ?? 'flat'}
						</span>
					</div>
				</div>
			{/if}

			<!-- Status mix (14d context) -->
			{#if historicalStatusMix.length > 0}
				<div class="history-section">
					<h3 class="history-section-title">Status Mix (14 days)</h3>
					<div class="flex h-5 rounded overflow-hidden mb-1">
						{#each historicalStatusMix as bucket}
							<div
								class="flex items-center justify-center text-[9px] font-medium text-white/90"
								style="width:{bucket.pct}%; background-color:{bucket.label === 'Balanced' ? '#4CAF82' : bucket.label === 'Low' ? '#E85D4A' : bucket.label === 'Unbalanced' ? '#D4944C' : '#8a9baa'};"
								title="{bucket.label}: {bucket.count} days ({bucket.pct}%)"
							>
								{#if bucket.pct >= 12}{bucket.pct}%{/if}
							</div>
						{/each}
					</div>
					<div class="flex gap-3 flex-wrap">
						{#each historicalStatusMix as bucket}
							<span class="text-[10px] text-[#6b7d8e]">{bucket.label}: {bucket.count}d</span>
						{/each}
					</div>
				</div>
			{/if}

			<!-- Recovery Insights -->
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
		<div class="range-picker">
			{#each TREND_RANGES as r}
				<button
					class="range-btn"
					class:active={trendRange === r}
					onclick={() => (trendRange = r)}
				>{r}</button>
			{/each}
		</div>
	</div>

	<!-- Nightly HRV Trend + Weekly Boxplot — side by side -->
	<div class="two-col-row">
		{#if nightlyTrendConfig}
			<div class="card two-col-item">
				<h2 class="card-title">Nightly HRV — Click to Explore <span class="info-hint" data-tip="Click any point to explore that night. Thick line = 7-day moving average. Shaded band = your typical range.">ⓘ</span></h2>
				<LineChart config={nightlyTrendConfig} height={260} />
			</div>
		{/if}

		{#if boxplotConfig}
			<div class="card two-col-item">
				<h2 class="card-title">Nightly HRV — Weekly Spread <span class="info-hint" data-tip="How much your nightly HRV varies each week. Narrow band = consistent. Wide band = variable.">ⓘ</span></h2>
				<LineChart config={boxplotConfig} height={260} />
				<p class="card-footnote">Shaded band = middle 50% of nights · dashes = extremes · bold line = median</p>
			</div>
		{/if}
	</div>

	<!-- Distribution + Day of Week — side by side -->
	<div class="section-subheader">
		<span class="section-sublabel">Patterns</span>
	</div>

	<div class="two-col-row">
		{#if distributionConfig}
			<div class="card two-col-item">
				<h2 class="card-title">HRV Distribution <span class="info-hint" data-tip="Where your nightly HRV typically falls. Highlighted bin = selected night.">ⓘ</span></h2>
				<BarChart config={distributionConfig} height={220} />
				{#if distribution}
					<p class="card-footnote">
						{distribution.total_days} nights{#if distribution.selected_percentile != null} · selected night at {distribution.selected_percentile}th percentile{/if}
					</p>
				{/if}
			</div>
		{/if}

		{#if dayOfWeekConfig}
			<div class="card two-col-item">
				<h2 class="card-title">HRV by Day of Week <span class="info-hint" data-tip="Average nightly HRV by weekday. Higher bars = better recovery on those nights.">ⓘ</span></h2>
				<BarChart config={dayOfWeekConfig} height={220} />
				<p class="card-footnote">{dayOfWeek.reduce((sum, b) => sum + b.sample_count, 0)} total nights</p>
			</div>
		{/if}
	</div>

	<!-- Reading Guide -->
	<MetricDefinition title="How to Read This Dashboard">
		<div class="reading-guide">
			<div class="guide-section">
				<strong class="guide-heading">Tonight (top)</strong>
				<p>Your overnight snapshot. Nightly HRV is measured during sleep — it's the most reliable window into autonomic function. The recovery pill shows whether you're above or below your 7-day baseline.</p>
			</div>
			<div class="guide-section">
				<strong class="guide-heading">History strip</strong>
				<p>Green = Balanced · Orange = Unbalanced · Red = Low. Each block is one night. Click any block to drill into that night's data, trajectory, and recovery insights.</p>
			</div>
			<div class="guide-section">
				<strong class="guide-heading">Trend charts — the bold line is the signal</strong>
				<p>Raw nightly values are noisy. The thick 7-day moving average reveals the real trend — watch it for multi-week drift up or down. Click any point to explore that night.</p>
			</div>
			<div class="guide-section">
				<strong class="guide-heading">Weekly spread — consistency is the goal</strong>
				<p>A narrow, stable band means your HRV baseline is consistent. A widening band or dropping median may signal accumulated stress, poor sleep, or overtraining.</p>
			</div>
			<div class="guide-section">
				<strong class="guide-heading">What affects HRV</strong>
				<p>Poor sleep, alcohol, illness, overtraining, and stress lower HRV. Good sleep, fitness, relaxation, and recovery raise it. Trends matter more than any single night.</p>
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
		justify-content: space-between;
	}
	.range-picker {
		display: flex;
		gap: 4px;
	}
	.range-btn {
		padding: 3px 10px;
		font-size: 11px;
		font-family: 'DM Mono', monospace;
		font-weight: 400;
		color: #6b7d8e;
		background: transparent;
		border: 1px solid rgba(255,255,255,0.1);
		border-radius: 4px;
		cursor: pointer;
		transition: all 0.15s;
	}
	.range-btn:hover {
		color: #c8d6e0;
		border-color: rgba(255,255,255,0.2);
	}
	.range-btn.active {
		color: #c8d6e0;
		background: rgba(255,255,255,0.08);
		border-color: rgba(255,255,255,0.2);
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

	/* ── Two-column layout ── */
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
		border: 1px solid rgba(155,107,205,0.15);
		border-left: 3px solid rgba(155,107,205,0.4);
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

	/* ── Trajectory mini-bar ── */
	.trajectory-bar {
		display: flex;
		align-items: flex-end;
		gap: 12px;
		height: 80px;
		padding: 4px 0;
	}
	.trajectory-segment {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 4px;
		flex: 1;
		height: 100%;
		justify-content: flex-end;
	}
	.trajectory-fill {
		width: 100%;
		max-width: 40px;
		border-radius: 3px 3px 0 0;
		transition: height 0.3s;
	}
	.trajectory-val {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #c8d6e0;
		font-weight: 500;
	}
	.trajectory-label {
		font-size: 10px;
		color: #5e7282;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}
	.trajectory-direction {
		font-family: 'DM Mono', monospace;
		font-size: 13px;
		font-weight: 600;
		align-self: center;
		white-space: nowrap;
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
		.two-col-row { flex-direction: column; }
	}
</style>
