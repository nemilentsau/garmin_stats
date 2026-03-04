<script lang="ts">
	import { onMount } from 'svelte';
	import { slide } from 'svelte/transition';
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
	import DoughnutChart from '$lib/components/DoughnutChart.svelte';
	import MetricDefinition from '$lib/components/MetricDefinition.svelte';
	import { fmt } from '$lib/format';
	import { COLORS, withAlpha } from '$lib/colors';
	import type { ChartConfiguration } from 'chart.js';

	// ── State ──
	let agg: DailyAggregates | null = $state(null);
	let analysis: HRAnalysis | null = $state(null);
	let loading = $state(true);
	let error: string | null = $state(null);

	// Latest day (Tier 1 — always the most recent)
	let latestInsights: HeartRateInsights | null = $state(null);
	let latestIntraday: WellnessData | null = $state(null);

	// Historical day (Tier 2 — selected via bar)
	let selectedDate = $state('');
	let historyOpen = $state(false);
	let historicalInsights: HeartRateInsights | null = $state(null);
	let historicalIntraday: WellnessData | null = $state(null);
	let historicalDistribution: HRDistribution | null = $state(null);
	let dateRequestId = 0;

	// ── Data fetching ──
	async function fetchData() {
		const [nextAgg, nextAnalysis] = await Promise.all([
			api.getDailyAggregates(),
			api.getHeartRateAnalysis()
		]);
		agg = nextAgg;
		analysis = nextAnalysis;

		// Always fetch latest day data for Tier 1
		if (nextAgg.days.length > 0) {
			const latest = nextAgg.days[nextAgg.days.length - 1];
			const [ins, intra] = await Promise.all([
				api.getHeartRateInsights(latest),
				api.getWellness(latest)
			]);
			latestInsights = ins;
			latestIntraday = intra;
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
				api.getWellness(date),
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
		selectedDate = '';
		historyOpen = false;
		historicalInsights = null;
		historicalIntraday = null;
		historicalDistribution = null;
	}

	// ── Derived: Latest day (Tier 1) ──
	let latestDate = $derived.by(() => agg?.days[agg.days.length - 1] ?? '');
	let latestDayStats = $derived.by(() => latestInsights?.day_stats ?? null);
	let latestRecovery = $derived.by(() => latestInsights?.recovery ?? null);

	let latestStats = $derived.by(() => {
		if (!agg?.period) return null;
		const hr = agg.period.heart_rate;
		return { overallAvg: hr.avg, typicalLow: hr.typical_low, typicalHigh: hr.typical_high, avgResting: hr.avg_resting };
	});

	let latestZoneBreakdown = $derived.by(() => {
		if (!latestInsights || latestInsights.zones.length === 0) return null;
		return latestInsights.zones.map((z) => ({
			label: z.label,
			color: ZONE_COLORS[z.label] ?? '#6b7d8e',
			pct: z.pct,
			minutes: z.minutes
		}));
	});

	// ── Derived: Historical day (Tier 2) ──
	let historicalDayStats = $derived.by(() => historicalInsights?.day_stats ?? null);
	let historicalRecovery = $derived.by(() => historicalInsights?.recovery ?? null);

	let historicalZoneBreakdown = $derived.by(() => {
		if (!historicalInsights || historicalInsights.zones.length === 0) return null;
		return historicalInsights.zones.map((z) => ({
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
		const avgResting = agg.period?.heart_rate.avg_resting;
		if (avgResting == null) return map;
		for (const d of agg.daily) {
			const rhr = d.heart_rate.resting;
			if (rhr == null) { map.set(d.date, '#3a4a5a'); continue; }
			const delta = rhr - avgResting;
			if (delta > 5) map.set(d.date, '#E85D4A');
			else if (delta > 2) map.set(d.date, '#D4944C');
			else map.set(d.date, '#4CAF82');
		}
		return map;
	});

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

	function fmtSigned(n: number | null | undefined): string {
		if (n == null) return '-';
		const rounded = n.toFixed(1);
		return n > 0 ? `+${rounded}` : rounded;
	}

	function recoveryColor(status: string | null | undefined): string {
		if (status === 'high' || status === 'elevated') return '#E85D4A';
		if (status === 'low' || status === 'normal') return '#4CAF82';
		return '#8a9baa';
	}

	function insightColor(level: string): string {
		if (level === 'warning') return '#E85D4A';
		if (level === 'caution') return '#D4944C';
		if (level === 'good') return '#4CAF82';
		return '#8a9baa';
	}

	// ── Shared chart config ──
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

	// ── Chart: Latest Intraday ──
	let latestIntradayConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!latestIntraday || latestIntraday.heart_rate.length === 0) return null;
		const datasets: ChartConfiguration<'line'>['data']['datasets'] = [
			{
				label: 'Heart Rate',
				data: latestIntraday.heart_rate.map((d) => d.value),
				borderColor: COLORS.heartRate,
				borderWidth: 1.5,
				pointRadius: 0,
				tension: 0.2,
				fill: false
			}
		];
		if (latestDayStats?.resting != null) {
			datasets.push({
				label: 'Resting HR',
				data: latestIntraday.heart_rate.map(() => latestDayStats!.resting!),
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
				labels: latestIntraday.heart_rate.map((d) => d.timestamp),
				datasets
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: datasets.length > 1, labels: { boxWidth: 12, font: { size: 11 }, color: '#8a9baa' } },
					tooltip: { backgroundColor: '#1a2332', borderWidth: 1, borderColor: withAlpha(COLORS.heartRate, '60'), padding: 10, cornerRadius: 4 },
					annotation: {
						annotations: {
							restZone: { type: 'box', yMin: 0, yMax: 60, backgroundColor: 'rgba(74,111,165,0.06)', borderWidth: 0, adjustScaleRange: false },
							lightZone: { type: 'box', yMin: 60, yMax: 100, backgroundColor: 'rgba(76,175,130,0.05)', borderWidth: 0, adjustScaleRange: false },
							modZone: { type: 'box', yMin: 100, yMax: 140, backgroundColor: 'rgba(212,148,76,0.05)', borderWidth: 0, adjustScaleRange: false },
							vigZone: { type: 'box', yMin: 140, yMax: 220, backgroundColor: 'rgba(232,93,74,0.05)', borderWidth: 0, adjustScaleRange: false }
						}
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
						title: { display: true, text: 'bpm', color: '#6b7d8e' },
						ticks: { color: '#6b7d8e' },
						grid: { color: '#ffffff06' },
						border: { color: '#ffffff10' }
					}
				}
			}
		};
	});

	// ── Chart: Historical Intraday ──
	let historicalIntradayConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!historicalIntraday || historicalIntraday.heart_rate.length === 0) return null;
		const datasets: ChartConfiguration<'line'>['data']['datasets'] = [
			{
				label: 'Heart Rate',
				data: historicalIntraday.heart_rate.map((d) => d.value),
				borderColor: COLORS.heartRate,
				borderWidth: 1.5,
				pointRadius: 0,
				tension: 0.2,
				fill: false
			}
		];
		if (historicalDayStats?.resting != null) {
			datasets.push({
				label: 'Resting HR',
				data: historicalIntraday.heart_rate.map(() => historicalDayStats!.resting!),
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
				labels: historicalIntraday.heart_rate.map((d) => d.timestamp),
				datasets
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: datasets.length > 1, labels: { boxWidth: 12, font: { size: 11 }, color: '#8a9baa' } },
					tooltip: { backgroundColor: '#1a2332', borderWidth: 1, borderColor: withAlpha(COLORS.heartRate, '60'), padding: 10, cornerRadius: 4 },
					annotation: {
						annotations: {
							restZone: { type: 'box', yMin: 0, yMax: 60, backgroundColor: 'rgba(74,111,165,0.06)', borderWidth: 0, adjustScaleRange: false },
							lightZone: { type: 'box', yMin: 60, yMax: 100, backgroundColor: 'rgba(76,175,130,0.05)', borderWidth: 0, adjustScaleRange: false },
							modZone: { type: 'box', yMin: 100, yMax: 140, backgroundColor: 'rgba(212,148,76,0.05)', borderWidth: 0, adjustScaleRange: false },
							vigZone: { type: 'box', yMin: 140, yMax: 220, backgroundColor: 'rgba(232,93,74,0.05)', borderWidth: 0, adjustScaleRange: false }
						}
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
						title: { display: true, text: 'bpm', color: '#6b7d8e' },
						ticks: { color: '#6b7d8e' },
						grid: { color: '#ffffff06' },
						border: { color: '#ffffff10' }
					}
				}
			}
		};
	});

	// ── Chart: Doughnut (zone breakdown) ──
	function makeDoughnutConfig(zones: typeof latestZoneBreakdown): ChartConfiguration<'doughnut'> | null {
		if (!zones || zones.length === 0) return null;
		return {
			type: 'doughnut',
			data: {
				labels: zones.map((z) => z.label),
				datasets: [{
					data: zones.map((z) => z.minutes),
					backgroundColor: zones.map((z) => z.color),
					borderColor: 'rgba(13,21,32,0.95)',
					borderWidth: 2,
					hoverBorderColor: '#1a2332'
				}]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				cutout: '62%',
				plugins: {
					legend: { display: false },
					tooltip: {
						backgroundColor: '#1a2332',
						borderWidth: 1,
						borderColor: 'rgba(255,255,255,0.1)',
						padding: 10,
						cornerRadius: 4,
						callbacks: {
							label: (ctx) => {
								const zone = zones[ctx.dataIndex];
								return `${zone.label}: ${zone.minutes}m (${zone.pct}%)`;
							}
						}
					}
				}
			}
		};
	}

	let latestDoughnutConfig = $derived.by(() => makeDoughnutConfig(latestZoneBreakdown));
	let historicalDoughnutConfig = $derived.by(() => makeDoughnutConfig(historicalZoneBreakdown));

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
					if (typeof label !== 'string') return;
					if (label === selectedDate) {
						closeHistory();
					} else {
						void onDateChange(label);
					}
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
					borderColor: '#6366B0', borderWidth: 2, pointRadius: 2,
					pointBackgroundColor: '#6366B0', tension: 0.3, spanGaps: true,
					fill: { target: 'origin', above: 'rgba(99, 102, 176, 0.12)' }
				}]
			},
			options: {
				responsive: true, maintainAspectRatio: false,
				plugins: { legend: { display: false }, tooltip: { backgroundColor: '#1a2332', borderWidth: 1, borderColor: 'rgba(99, 102, 176, 0.6)', padding: 10, cornerRadius: 4 } },
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
				plugins: { legend: { display: false }, tooltip: { backgroundColor: '#1a2332', borderWidth: 1, borderColor: withAlpha(COLORS.heartRate, '60'), padding: 10, cornerRadius: 4 } },
				scales: {
					x: { title: { display: true, text: 'Hour of Day', color: '#6b7d8e' }, ticks: { font: { size: 10 }, color: '#6b7d8e' }, grid: { color: '#ffffff08' }, border: { color: '#ffffff10' } },
					y: { beginAtZero: false, title: { display: true, text: 'bpm', color: '#6b7d8e' }, ticks: { color: '#6b7d8e' }, grid: { color: '#ffffff06' }, border: { color: '#ffffff10' } }
				}
			}
		};
	});

	// ── Chart: Distribution ──
	let distributionConfig = $derived.by<ChartConfiguration<'bar'> | null>(() => {
		if (!historicalDistribution || historicalDistribution.bins.length === 0) return null;
		return {
			type: 'bar',
			data: {
				labels: historicalDistribution.bins.map((b) => `${b.bin_start}–${b.bin_end}`),
				datasets: [{
					label: 'Readings', data: historicalDistribution.bins.map((b) => b.count),
					backgroundColor: withAlpha(COLORS.heartRate, '70'), borderColor: COLORS.heartRate,
					borderWidth: 1, borderRadius: 2
				}]
			},
			options: {
				responsive: true, maintainAspectRatio: false,
				plugins: { legend: { display: false }, tooltip: { backgroundColor: '#1a2332', borderWidth: 1, borderColor: withAlpha(COLORS.heartRate, '60'), padding: 10, cornerRadius: 4 } },
				scales: {
					x: { title: { display: true, text: 'bpm range', color: '#6b7d8e' }, ticks: { maxRotation: 45, font: { size: 10 }, color: '#6b7d8e' }, grid: { color: '#ffffff08' }, border: { color: '#ffffff10' } },
					y: { beginAtZero: true, title: { display: true, text: 'count', color: '#6b7d8e' }, ticks: { color: '#6b7d8e' }, grid: { color: '#ffffff06' }, border: { color: '#ffffff10' } }
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
				{fmt(latestStats?.avgResting)}
			</span>
			<span class="stat-unit">bpm</span>
			{#if latestRecovery?.delta_from_baseline != null}
				<span class="stat-delta" style="color: {recoveryColor(latestRecovery?.status)};">
					{fmtSigned(latestRecovery.delta_from_baseline)} vs 7d
				</span>
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
		</div>
		<div class="stat-item">
			<span class="stat-label">Range</span>
			<span class="stat-value" style="color: #c8d6e0;">
				{fmt(latestStats?.typicalLow)}–{fmt(latestStats?.typicalHigh)}
			</span>
			<span class="stat-unit">bpm</span>
		</div>
	</div>

	<!-- Insight line — latest day -->
	{#if latestInsights && latestInsights.insights.length > 0}
		{@const topInsight = latestInsights.insights[0]}
		<div class="insight-line">
			<span class="insight-dot" style="background: {insightColor(topInsight.level)};"></span>
			<span class="insight-level" style="color: {insightColor(topInsight.level)};">{topInsight.level.toUpperCase()}</span>
			<span class="insight-text">{topInsight.title}</span>
			<span class="insight-detail">{topInsight.detail}</span>
		</div>
	{/if}

	<!-- Intraday chart — latest day -->
	{#if latestIntradayConfig}
		<div class="card">
			<h2 class="card-title">Intraday Heart Rate</h2>
			<LineChart config={latestIntradayConfig} height={280} />
			<p class="card-footnote">{latestIntraday?.heart_rate.length ?? 0} readings</p>
		</div>
	{/if}

	<!-- Donut + Day Stats — latest day -->
	{#if latestZoneBreakdown && latestDoughnutConfig}
		<div class="zones-stats-row">
			<div class="card donut-card">
				<h2 class="card-title">HR Zones</h2>
				<div class="donut-layout">
					<div class="donut-chart-wrap">
						<DoughnutChart config={latestDoughnutConfig} height={160} />
					</div>
					<div class="zone-legend-vertical">
						{#each latestZoneBreakdown as zone}
							<span class="zone-item">
								<i class="legend-dot" style="background: {zone.color};"></i>
								<span class="zone-label-text">{zone.label}</span>
								<span class="zone-time">{fmt(zone.minutes)}m</span>
								<span class="zone-pct-label">{zone.pct}%</span>
							</span>
						{/each}
					</div>
				</div>
			</div>
			{#if latestDayStats}
				<div class="card day-stats-card">
					<h2 class="card-title">Day Stats</h2>
					<div class="mini-stat-grid">
						<div class="mini-stat"><span class="mini-label">Min</span><span class="mini-value" style="color:#4A90D9">{fmt(latestDayStats.min)}</span></div>
						<div class="mini-stat"><span class="mini-label">Max</span><span class="mini-value" style="color:#D4944C">{fmt(latestDayStats.max)}</span></div>
						<div class="mini-stat"><span class="mini-label">Avg</span><span class="mini-value" style="color:#E85D4A">{fmt(latestDayStats.avg)}</span></div>
						<div class="mini-stat"><span class="mini-label">Median</span><span class="mini-value">{fmt(latestDayStats.median)}</span></div>
						<div class="mini-stat"><span class="mini-label">Resting</span><span class="mini-value" style="color:#4CAF82">{fmt(latestDayStats.resting)}</span></div>
					</div>
				</div>
			{/if}
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
					<h3 class="history-section-title">Intraday Heart Rate</h3>
					<LineChart config={historicalIntradayConfig} height={240} />
					<p class="card-footnote">{historicalIntraday?.heart_rate.length ?? 0} readings</p>
				</div>
			{:else if !historicalIntraday}
				<div class="text-sm text-[#5e7282] py-4">Loading intraday data...</div>
			{/if}

			{#if historicalZoneBreakdown && historicalDoughnutConfig}
				<div class="zones-stats-row history-zones-row">
					<div class="history-subsection donut-card">
						<h3 class="history-section-title">HR Zones</h3>
						<div class="donut-layout">
							<div class="donut-chart-wrap">
								<DoughnutChart config={historicalDoughnutConfig} height={140} />
							</div>
							<div class="zone-legend-vertical">
								{#each historicalZoneBreakdown as zone}
									<span class="zone-item">
										<i class="legend-dot" style="background: {zone.color};"></i>
										<span class="zone-label-text">{zone.label}</span>
										<span class="zone-time">{fmt(zone.minutes)}m</span>
										<span class="zone-pct-label">{zone.pct}%</span>
									</span>
								{/each}
							</div>
						</div>
					</div>
					{#if historicalDayStats}
						<div class="history-subsection day-stats-card">
							<h3 class="history-section-title">Day Stats</h3>
							<div class="mini-stat-grid">
								<div class="mini-stat"><span class="mini-label">Min</span><span class="mini-value" style="color:#4A90D9">{fmt(historicalDayStats.min)}</span></div>
								<div class="mini-stat"><span class="mini-label">Max</span><span class="mini-value" style="color:#D4944C">{fmt(historicalDayStats.max)}</span></div>
								<div class="mini-stat"><span class="mini-label">Avg</span><span class="mini-value" style="color:#E85D4A">{fmt(historicalDayStats.avg)}</span></div>
								<div class="mini-stat"><span class="mini-label">Median</span><span class="mini-value">{fmt(historicalDayStats.median)}</span></div>
								<div class="mini-stat"><span class="mini-label">Resting</span><span class="mini-value" style="color:#4CAF82">{fmt(historicalDayStats.resting)}</span></div>
							</div>
						</div>
					{/if}
				</div>
			{/if}

			{#if distributionConfig}
				<div class="history-section">
					<h3 class="history-section-title">HR Distribution</h3>
					<BarChart config={distributionConfig} height={220} />
					<p class="card-footnote">{historicalDistribution?.sample_count ?? 0} readings</p>
				</div>
			{/if}

			{#if historicalInsights && historicalInsights.insights.length > 0}
				<div class="history-section">
					<h3 class="history-section-title">Recovery Insights</h3>
					<div class="insights-list">
						{#each historicalInsights.insights as item}
							<div class="insight-card" style="border-left-color: {insightColor(item.level)};">
								<div class="insight-card-level" style="color: {insightColor(item.level)};">{item.level}</div>
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
	</div>

	<!-- Heart Rate Trends -->
	{#if trendConfig}
		<div class="card">
			<h2 class="card-title">Daily Avg & Resting HR — Click a day to explore</h2>
			<LineChart config={trendConfig} height={300} />
		</div>
	{/if}

	{#if restingTrendConfig}
		<div class="card">
			<h2 class="card-title">Resting HR — 7-Day Moving Average</h2>
			<LineChart config={restingTrendConfig} height={260} />
		</div>
	{/if}

	<!-- Sleep & Recovery -->
	<div class="section-subheader">
		<span class="section-sublabel">Sleep & Recovery</span>
	</div>

	{#if sleepingHRConfig}
		<div class="card">
			<h2 class="card-title">Sleeping HR Trend</h2>
			<LineChart config={sleepingHRConfig} height={260} />
			<p class="card-footnote">Average HR during light/deep/REM sleep stages (excludes awake)</p>
		</div>
	{/if}

	{#if circadianConfig}
		<div class="card">
			<h2 class="card-title">Circadian HR Profile</h2>
			<LineChart config={circadianConfig} height={260} />
			<p class="card-footnote">Average heart rate by hour of day across the entire period</p>
		</div>
	{/if}

	<!-- Analysis -->
	<div class="section-subheader">
		<span class="section-sublabel">Analysis</span>
	</div>

	{#if boxplotConfig}
		<div class="card">
			<h2 class="card-title">Weekly Resting HR — Boxplot</h2>
			<LineChart config={boxplotConfig} height={260} />
			<p class="card-footnote">Min / Q1 / Median / Q3 / Max of daily resting HR per ISO week</p>
		</div>
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
	.history-subsection {
		margin-bottom: 0;
	}
	.history-zones-row {
		margin-top: 16px;
		padding-top: 16px;
		border-top: 1px solid rgba(255,255,255,0.04);
		margin-bottom: 0;
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

	/* ── Donut + Stats row ── */
	.zones-stats-row {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: 14px;
		margin-bottom: 14px;
	}
	.donut-card { margin-bottom: 0; }
	.day-stats-card { margin-bottom: 0; min-width: 180px; }

	.donut-layout {
		display: flex;
		align-items: center;
		gap: 20px;
	}
	.donut-chart-wrap {
		width: 160px;
		flex-shrink: 0;
	}
	.zone-legend-vertical {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.zone-item {
		font-size: 11px;
		color: #8a9baa;
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.zone-label-text {
		width: 64px;
	}
	.zone-time {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #c8d6e0;
		min-width: 44px;
		text-align: right;
	}
	.zone-pct-label {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		color: #5e7282;
		min-width: 32px;
		text-align: right;
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
		.donut-layout { flex-direction: column; align-items: flex-start; }
		.donut-chart-wrap { width: 140px; }
	}
</style>
