<script lang="ts">
	import { onMount } from 'svelte';
	import { slide } from 'svelte/transition';
	import { replaceState } from '$app/navigation';
	import {
		api,
		type HrvDaily,
		type DashboardOverview,
		type HrvInsights,
		type HrvAnalysis
	} from '$lib/api';
	import { startRealtimePage } from '$lib/realtime-page';
	import {
		DEFAULT_HRV_BASELINE_WINDOW,
		coerceHrvBaselineWindow,
		type HrvBaselineWindow
	} from '$lib/hrv-baseline';
	import LineChart from '$lib/components/LineChart.svelte';
	import BarChart from '$lib/components/BarChart.svelte';
	import { fmt, fmtSigned } from '$lib/format';
	import { fmtFullDate, parseIsoDate } from '$lib/date';
	import { COLORS, withAlpha, insightLevelColor } from '$lib/colors';
	import { chartTooltip, DARK_GRID, DARK_GRID_Y, DARK_BORDER, DARK_TICK } from '$lib/chart-setup';
	import TrendRangePicker from '$lib/components/TrendRangePicker.svelte';
	import BaselineWindowPicker from '$lib/components/BaselineWindowPicker.svelte';
	import { type TrendRange, trendCutoff, PERIOD_KEY_MAP } from '$lib/trend-range';
	import type { ChartConfiguration } from 'chart.js';
	import { tightScale } from '$lib/chart-scale';

	// ── State ──
	let agg: HrvDaily | null = $state(null);
	let analysis: HrvAnalysis | null = $state(null);
	let dashOverview: DashboardOverview | null = $state(null);
	let loading = $state(true);
	let baselineLoading = $state(false);
	let error: string | null = $state(null);
	// Non-blocking error scoped to a single failed sub-fetch (night detail / baseline
	// refresh). Kept separate from `error` so one failed secondary request never blanks
	// the already-loaded dashboard.
	let detailError = $state<string | null>(null);

	// Latest day (Tier 1 — always the most recent)
	let latestInsights: HrvInsights | null = $state(null);

	// Historical day (Tier 2 — selected via strip)
	let selectedDate = $state('');
	let historyOpen = $state(false);
	let dayHover: { date: string; x: number; y: number } | null = $state(null);
	let historicalInsights: HrvInsights | null = $state(null);
	let dateRequestId = 0;
	let baselineRequestId = 0;
	// Monotonic guard for fetchData itself: out-of-order completions (e.g. rapid
	// baseline-window switches) must not write a stale window's data under the new labels.
	let fetchSeq = 0;

	// ── Baseline window ──
	function readBaselineFromUrl(): HrvBaselineWindow {
		return coerceHrvBaselineWindow(new URL(window.location.href).searchParams.get('baseline'));
	}
	let baselineWindow = $state<HrvBaselineWindow>(DEFAULT_HRV_BASELINE_WINDOW);

	type HrvSnapshot = {
		agg: HrvDaily;
		analysis: HrvAnalysis;
		dashOverview: DashboardOverview;
		latestInsights: HrvInsights | null;
		historicalInsights: HrvInsights | null;
	};

	// ── Data fetching ──
	async function loadHrvSnapshot(
		window: HrvBaselineWindow,
		historicalDate = ''
	): Promise<HrvSnapshot> {
		const [nextAgg, nextAnalysis, nextOverview] = await Promise.all([
			api.getHrvDaily(),
			api.getHrvAnalysis(window),
			api.getDashboardOverview()
		]);
		const latest = nextAgg.days[nextAgg.days.length - 1] ?? '';
		const [nextLatestInsights, nextHistoricalInsights] = await Promise.all([
			latest ? api.getHrvInsights(latest, window) : Promise.resolve(null),
			historicalDate ? api.getHrvInsights(historicalDate, window) : Promise.resolve(null)
		]);
		return {
			agg: nextAgg,
			analysis: nextAnalysis,
			dashOverview: nextOverview,
			latestInsights: nextLatestInsights,
			historicalInsights: nextHistoricalInsights
		};
	}

	function applyHrvSnapshot(
		snapshot: HrvSnapshot,
		options: { applyHistorical?: boolean; clearDetailError?: boolean } = {}
	) {
		agg = snapshot.agg;
		analysis = snapshot.analysis;
		dashOverview = snapshot.dashOverview;
		latestInsights = snapshot.latestInsights;
		if (options.applyHistorical) {
			historicalInsights = snapshot.historicalInsights;
		}
		// A successful load supersedes any prior top-level error.
		error = null;
		if (options.clearDetailError ?? true) {
			detailError = null;
		}
	}

	async function fetchData() {
		const seq = ++fetchSeq;
		const snapshot = await loadHrvSnapshot(baselineWindow);
		if (seq !== fetchSeq) return;
		applyHrvSnapshot(snapshot, { clearDetailError: selectedDate === '' });
	}

	onMount(() => {
		baselineWindow = readBaselineFromUrl();
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
			detailError = null;
			return;
		}
		selectedDate = date;
		historyOpen = true;
		historicalInsights = null;
		detailError = null;
		const requestId = ++dateRequestId;
		try {
			const nextInsights = await api.getHrvInsights(date, baselineWindow);
			if (requestId !== dateRequestId) return;
			historicalInsights = nextInsights;
			detailError = null;
		} catch (e: unknown) {
			if (requestId !== dateRequestId) return;
			detailError = e instanceof Error ? e.message : String(e);
		}
	}

	function setBaselineUrl(w: HrvBaselineWindow) {
		const url = new URL(window.location.href);
		url.searchParams.set('baseline', String(w));
		replaceState(url, {});
	}

	async function onBaselineChange(w: HrvBaselineWindow) {
		const prev = baselineWindow;
		const selectedForBaseline = selectedDate;
		baselineWindow = w;
		setBaselineUrl(w);
		const requestId = ++baselineRequestId;
		baselineLoading = true;
		try {
			const snapshot = await loadHrvSnapshot(w, selectedForBaseline);
			if (requestId !== baselineRequestId) return;
			applyHrvSnapshot(snapshot, {
				applyHistorical: selectedForBaseline !== '' && selectedForBaseline === selectedDate,
				clearDetailError: selectedForBaseline === '' || selectedForBaseline === selectedDate
			});
		} catch (e: unknown) {
			if (requestId !== baselineRequestId) return;
			// Roll back to the last good window (state + URL) and surface a non-blocking
			// error so the dashboard keeps showing the prior window's data.
			baselineWindow = prev;
			setBaselineUrl(prev);
			detailError = e instanceof Error ? e.message : String(e);
		} finally {
			if (requestId === baselineRequestId) baselineLoading = false;
		}
	}

	function closeHistory() {
		selectedDate = '';
		historyOpen = false;
		historicalInsights = null;
		detailError = null;
	}

	function onTimelineKeydown(e: KeyboardEvent) {
		if (e.key === 'ArrowRight') {
			e.preventDefault();
			navigateDay(1);
		} else if (e.key === 'ArrowLeft') {
			e.preventDefault();
			navigateDay(-1);
		}
	}

	function showDayHover(e: MouseEvent, day: string) {
		dayHover = { date: day, x: e.clientX, y: e.clientY };
	}
	function moveDayHover(e: MouseEvent) {
		if (dayHover) dayHover = { ...dayHover, x: e.clientX, y: e.clientY };
	}
	function hideDayHover() {
		dayHover = null;
	}

	// ── Computed: Latest day ──
	let latestDate = $derived.by(() => {
		if (!agg) return '';
		return agg.days[agg.days.length - 1] ?? '';
	});
	let latestDayStats = $derived.by(() => latestInsights?.day_stats ?? null);
	let latestRecovery = $derived.by(() => latestInsights?.recovery ?? null);
	let monthSegments = $derived.by(() => {
		const days = agg?.days ?? [];
		const segs: { month: string; label: string; count: number }[] = [];
		for (const d of days) {
			const month = d.slice(0, 7);
			const last = segs[segs.length - 1];
			if (last && last.month === month) {
				last.count += 1;
			} else {
				const dt = new Date(d + 'T00:00:00');
				let label = dt.toLocaleString('en-US', { month: 'short' });
				if (month.slice(5) === '01') label += ` '${month.slice(2, 4)}`;
				segs.push({ month, label, count: 1 });
			}
		}
		return segs;
	});

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

	// ── Trend time-window ──
	let trendRange: TrendRange = $state('3M');

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

	// ── Trend chart: Nightly HRV with 7-day MA ──
	let nightlyTrendConfig = $derived.by<ChartConfiguration<'line'> | null>(() => {
		if (!analysis || analysis.nightly_trend.length === 0) return null;
		const cutoff = trendCutoff(trendRange);
		const t = cutoff ? analysis.nightly_trend.filter((p) => p.date >= cutoff) : analysis.nightly_trend;
		const labels = t.map((p) => p.date);
		const datasets: ChartConfiguration<'line'>['data']['datasets'] = [
			{
				label: 'Band Low',
				data: t.map((p) => p.band_low),
				borderColor: withAlpha(COLORS.hrvWeekly, '30'),
				borderWidth: 1, pointRadius: 0, tension: 0.3, spanGaps: false, fill: false
			},
			{
				label: 'Band High',
				data: t.map((p) => p.band_high),
				borderColor: withAlpha(COLORS.hrvWeekly, '30'),
				borderWidth: 1, pointRadius: 0, tension: 0.3, spanGaps: false,
				fill: '-1', backgroundColor: withAlpha(COLORS.hrvWeekly, '14')
			},
			{
				label: '7-Day MA',
				data: t.map((p) => p.ma7),
				borderColor: COLORS.hrv, borderWidth: 2.5, pointRadius: 0, tension: 0.3, spanGaps: true
			},
			{
				label: 'Extreme night',
				data: t.map((p) => (p.is_extreme ? (p.z != null && p.z < 0 ? p.band_low : p.band_high) : null)),
				borderColor: 'transparent',
				backgroundColor: COLORS.heartRate,
				pointRadius: t.map((p) => (p.is_extreme ? 4 : 0)),
				pointHoverRadius: 5,
				showLine: false, spanGaps: false
			}
		];

		const yScale = tightScale(
			[
				...t.map((p) => p.ma7),
				...t.map((p) => p.band_low),
				...t.map((p) => p.band_high)
			],
			2,
			5
		);

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
					legend: { display: false },
					tooltip: {
						...darkPlugins.tooltip,
						callbacks: {
							title: (items) => {
								const idx = items[0]?.dataIndex;
								const raw = idx != null ? t[idx]?.date : null;
								return raw ? fmtFullDate(parseIsoDate(raw)) : '';
							},
							label: (ctx) => {
								if (ctx.dataset.label === 'Extreme night') {
									const p = t[ctx.dataIndex];
									if (!p?.is_extreme || p.nightly_avg == null) return undefined;
									return `Extreme night: ${p.nightly_avg} ms`;
								}
								return `${ctx.dataset.label}: ${ctx.formattedValue}`;
							}
						}
					}
				},
				scales: {
					x: {
						type: 'time',
						time: {
							unit: 'month',
							displayFormats: { month: "MMM ''yy" },
							parser: (v: unknown) => {
								// Parse the local YYYY-MM-DD label in local time (matching the
								// adapter's local formatting) so tooltips never show the prior day
								// in negative-offset timezones. Mirrors parseIsoDate in $lib/date.
								const [yy, mo, dd] = String(v).split('-').map(Number);
								return new Date(yy, mo - 1, dd).getTime();
							}
						},
						ticks: { maxRotation: 0, autoSkipPadding: 20, font: { size: 10 }, ...DARK_TICK },
						grid: DARK_GRID, border: DARK_BORDER
					},
					y: {
						beginAtZero: false,
						min: yScale?.min, max: yScale?.max,
						afterBuildTicks: yScale ? (axis) => { axis.ticks = yScale.ticks.map((value) => ({ value })); } : undefined,
						title: { display: true, text: 'ms', ...DARK_TICK },
						ticks: DARK_TICK, grid: DARK_GRID_Y, border: DARK_BORDER
					}
				}
			}
		};
	});

	// ── Pattern window (3M floor: 1M→3M, others pass through) ──
	let patternWindow = $derived.by(() => {
		const key = PERIOD_KEY_MAP[trendRange];
		return analysis?.pattern_windows?.[key] ?? null;
	});

	// Human label for the actual pattern window the card summarises. Because 1M floors
	// to the 3M window, the trend (≈30 days) and this card can span different ranges, so
	// we state the real span explicitly.
	let patternWindowLabel = $derived.by(() => {
		switch (PERIOD_KEY_MAP[trendRange]) {
			case '6M':
				return 'last 6 months';
			case 'All':
				return 'all time';
			default:
				return 'last 3 months';
		}
	});

	// ── Day of Week chart ──
	let dayOfWeek = $derived.by(() => patternWindow?.day_of_week ?? []);

	let dayOfWeekConfig = $derived.by<ChartConfiguration<'bar'> | null>(() => {
		if (dayOfWeek.length === 0) return null;
		// Backend-supplied grand mean (true sample-weighted reference); the frontend does
		// no statistical computation here. Null → neutral colouring for every bar.
		const overallAvg = patternWindow?.overall_avg ?? null;
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
	/** Signed 2-decimal format for correlation r-values (display only). */
	function fmtRValue(n: number | null | undefined): string {
		if (n == null) return '-';
		const r = n.toFixed(2);
		return n > 0 ? `+${r}` : r;
	}

	function recoveryColor(status: string | null | undefined): string {
		if (status === 'suppressed' || status === 'below_baseline') return '#E85D4A';
		if (status === 'elevated' || status === 'stable') return '#4CAF82';
		return '#6b7d8e';
	}

	// ── Correlations (from dashboard overview) ──
	type CorrelationItem = NonNullable<DashboardOverview['correlations']>[number];

	let coMovements = $derived.by(() => {
		const items = dashOverview?.correlations ?? [];
		return items
			.filter((c) => c.r_value != null)
			.slice()
			.sort((x, y) => Math.abs(y.r_value!) - Math.abs(x.r_value!));
	});

</script>

<svelte:head><title>HRV - Garmin Stats</title></svelte:head>

{#if !agg && error}
	<div class="bg-[rgba(232,93,74,0.08)] border border-[rgba(232,93,74,0.3)] rounded-lg p-4">
		<p class="text-[#E85D4A]">Error: {error}</p>
	</div>
{:else if !agg && loading}
	<div class="flex items-center justify-center h-64">
		<div class="text-[#5e7282]">Loading...</div>
	</div>
{:else if agg}

	<!-- ════════════════════════════════════════════════════ -->
	<!-- TIER 1: TONIGHT — headline + hero trend              -->
	<!-- ════════════════════════════════════════════════════ -->

	<div class="section-header">
		<span class="section-label">Tonight</span>
		<span class="section-date">{latestDate}</span>
	</div>

	<!-- Headline — latest night -->
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
	</div>

	<!-- Insight line — latest night -->
	{#if latestInsights && latestInsights.insights.length > 0}
		{@const topInsight = latestInsights.insights[0]}
		<div class="insight-line">
			<span class="insight-dot" style="background: {insightLevelColor(topInsight.level)};"></span>
			<span class="insight-level" style="color: {insightLevelColor(topInsight.level)};">{topInsight.level.toUpperCase()}</span>
			<span class="insight-text">{topInsight.title}</span>
			<span class="insight-detail">{topInsight.detail}</span>
		</div>
	{/if}

	<!-- Hero: nightly HRV trend (the multi-day signal) -->
	{#if nightlyTrendConfig}
		<div class="card hero-card" class:baseline-updating={baselineLoading}>
			<div class="hero-header">
				<h2 class="card-title">Nightly HRV trend <span class="info-hint" data-tip="Bold line = 7-day moving average. Shaded ribbon = your typical range over the chosen baseline window. Dots = nights outside that range. Click the line to open a night.">ⓘ</span></h2>
				<div class="hero-controls">
					<div class="control-group">
						<span class="control-label">Baseline</span>
						<BaselineWindowPicker value={baselineWindow} onchange={onBaselineChange} disabled={baselineLoading} />
					</div>
					<span class="control-sep" aria-hidden="true"></span>
					<div class="control-group">
						<span class="control-label">Show</span>
						<TrendRangePicker bind:value={trendRange} />
					</div>
				</div>
			</div>
			<LineChart config={nightlyTrendConfig} height={300} />
			<div class="chart-legend">
				<span class="lg"><i class="lg-line" style="background: {COLORS.hrv};"></i>7-day average</span>
				<span class="lg"><i class="lg-band" style="background: {withAlpha(COLORS.hrvWeekly, '22')}; border-color: {withAlpha(COLORS.hrvWeekly, '55')};"></i>typical range ({baselineWindow}d)</span>
				<span class="lg"><i class="lg-dot" style="background: {COLORS.heartRate};"></i>extreme night</span>
			</div>
			{#if latestInsights?.baseline?.delta_7d_vs_baseline != null}
				<p class="card-footnote">7-day average is {fmtSigned(latestInsights.baseline.delta_7d_vs_baseline)} ms vs your {latestInsights.baseline.window_days}-day baseline.</p>
			{/if}
		</div>
	{/if}

	<!-- ════════════════════════════════════════════════════ -->
	<!-- TIER 2: HISTORY TIMELINE + DETAIL                     -->
	<!-- ════════════════════════════════════════════════════ -->

	<div class="section-header tier2-header">
		<span class="section-label">History</span>
		<span class="section-sublabel">Click a night to explore · ← → to step</span>
	</div>

	<!-- Labelled timeline -->
	<div class="day-nav">
		<div class="day-nav-controls">
			<button class="nav-arrow" disabled={!canPrev} onclick={() => navigateDay(-1)}>←</button>
			<button class="day-label" onclick={() => closeHistory()}>
				{selectedDate || 'All Days'}
			</button>
			<button class="nav-arrow" disabled={!canNext} onclick={() => navigateDay(1)}>→</button>
		</div>
		<div class="day-strip-container">
			<div
				class="day-strip"
				role="toolbar"
				aria-orientation="horizontal"
				aria-label="HRV nightly timeline — left and right arrow keys step between nights"
				tabindex="0"
				onkeydown={onTimelineKeydown}
				onmousemove={moveDayHover}
				onmouseleave={hideDayHover}
			>
				{#each agg.days as day}
					<button
						class="day-cell"
						class:selected={day === selectedDate}
						style="background: {dayStatusMap.get(day) ?? '#3a4a5a'};"
						aria-label={day}
						onmouseenter={(e) => showDayHover(e, day)}
						onclick={() => onDateChange(day === selectedDate ? '' : day)}
					></button>
				{/each}
			</div>
			<div class="month-axis" aria-hidden="true">
				{#each monthSegments as seg}
					<span class="month-tick" style="flex: {seg.count};">{seg.label}</span>
				{/each}
			</div>
			<div class="day-strip-legend">
				<span><i class="legend-dot" style="background:#4CAF82;"></i>Balanced</span>
				<span><i class="legend-dot" style="background:#D4944C;"></i>Unbalanced</span>
				<span><i class="legend-dot" style="background:#E85D4A;"></i>Low</span>
			</div>
		</div>
	</div>

	{#if dayHover}
		<div class="day-tooltip" style="left: {dayHover.x}px; top: {dayHover.y}px;">{dayHover.date}</div>
	{/if}

	<!-- Expandable night detail -->
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

			{#if detailError}
				<div class="detail-error">Couldn't load this night: {detailError}</div>
			{:else if !historicalInsights}
				<div class="text-sm text-[#5e7282] py-4">Loading night data...</div>
			{/if}

			<!-- Where this night ranks (trailing-window z-score) -->
			{#if historicalInsights?.baseline?.selected_z != null}
				<div class="history-section">
					<h3 class="history-section-title">Where this night ranks</h3>
					<p class="percentile-readout">
						<strong>{fmtSigned(historicalInsights.baseline.selected_z)} SD</strong>
						vs your {historicalInsights.baseline.window_days}-day baseline
						{#if historicalInsights.baseline.selected_is_extreme}
							· <span style="color: {COLORS.heartRate};">extreme night</span>
						{/if}
					</p>
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
	<!-- TIER 3: PATTERNS                                      -->
	<!-- ════════════════════════════════════════════════════ -->

	<div class="section-header tier3-header">
		<span class="section-label">Patterns</span>
	</div>

	<!-- Day of week -->
	<div class="two-col-row">
		{#if dayOfWeekConfig}
			<div class="card two-col-item">
				<h2 class="card-title">By day of week <span class="info-hint" data-tip="Average nightly HRV by weekday. A weekly rhythm describes long-run averages, not any single night.">ⓘ</span></h2>
				<BarChart config={dayOfWeekConfig} height={240} />
				<p class="card-footnote">{dayOfWeek.reduce((sum, b) => sum + b.sample_count, 0)} total nights ({patternWindowLabel}) · weekday averages, not single-night predictions</p>
			</div>
		{/if}
	</div>

	<!-- What moves with HRV (co-movement, not cause) -->
	{#if coMovements.length > 0}
		<div class="section-subheader">
			<span class="section-sublabel">What moves with HRV</span>
		</div>
		<div class="card">
			<p class="comove-caption">These recovery metrics co-move with nightly HRV — shown as correlation strength and direction. Association, not cause.</p>
			<div class="comove-list">
				{#each coMovements as corr}
					<div class="comove-row">
						<span class="comove-label">{corr.label}</span>
						<div class="comove-track">
							<div class="comove-fill" style="width: {Math.abs(corr.r_value ?? 0) * 100}%; background: {(corr.r_value ?? 0) >= 0 ? COLORS.hrv : COLORS.heartRate};"></div>
						</div>
						<span class="comove-r">{fmtRValue(corr.r_value)}</span>
						<span class="comove-n">{corr.sample_count}n</span>
					</div>
				{/each}
			</div>
		</div>
	{/if}
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
		grid-template-columns: repeat(2, 1fr);
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
		gap: 0;
		padding: 2px 0;
	}
	.day-strip::-webkit-scrollbar { display: none; }

	.day-cell {
		flex: 1;
		min-width: 0;
		height: 28px;
		border-radius: 0;
		border: none;
		cursor: pointer;
		transition: all 0.12s;
		opacity: 0.9;
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

	/* ── Scoped (non-blocking) detail error ── */
	.detail-error {
		font-size: 12px;
		color: #E85D4A;
		background: rgba(232,93,74,0.08);
		border: 1px solid rgba(232,93,74,0.25);
		border-radius: 6px;
		padding: 8px 12px;
		margin: 4px 0 4px;
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

	/* ── Hero trend: in-flight baseline refresh ── */
	.hero-card.baseline-updating {
		opacity: 0.6;
		transition: opacity 0.15s;
	}
	.hero-card {
		transition: opacity 0.15s;
	}

	/* ── Hero trend header ── */
	.hero-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 12px;
		margin-bottom: 8px;
	}
	.hero-header .card-title { margin-bottom: 0; }
	.hero-controls {
		display: flex;
		align-items: center;
		gap: 14px;
		flex-wrap: wrap;
	}
	.control-group {
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.control-label {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 1px;
		color: #5e7282;
		white-space: nowrap;
	}
	.control-sep {
		width: 1px;
		height: 16px;
		background: rgba(255,255,255,0.1);
		flex-shrink: 0;
	}

	/* ── Month axis under timeline ── */
	.month-axis {
		display: flex;
		gap: 0;
		margin-top: 4px;
	}
	.month-tick {
		min-width: 0;
		overflow: hidden;
		white-space: nowrap;
		font-family: 'DM Mono', monospace;
		font-size: 9px;
		color: #5e7282;
		border-left: 1px solid rgba(255,255,255,0.06);
		padding-left: 2px;
	}

	/* ── Selected-night percentile ── */
	.percentile-readout {
		font-size: 13px;
		color: #c8d6e0;
	}
	.percentile-readout strong {
		font-family: 'DM Mono', monospace;
		font-variant-numeric: tabular-nums;
	}

	/* ── Co-movement summary ── */
	.comove-caption {
		font-size: 12px;
		color: #6b7d8e;
		margin-bottom: 12px;
	}
	.comove-list {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.comove-row {
		display: grid;
		grid-template-columns: 132px 1fr 56px 40px;
		align-items: center;
		gap: 10px;
	}
	.comove-label {
		font-size: 12px;
		color: #c8d6e0;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.comove-track {
		height: 10px;
		background: rgba(255,255,255,0.04);
		border-radius: 5px;
		overflow: hidden;
	}
	.comove-fill {
		height: 100%;
		border-radius: 5px;
	}
	.comove-r {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		font-variant-numeric: tabular-nums;
		color: #d9e5ec;
		text-align: right;
	}
	.comove-n {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		font-variant-numeric: tabular-nums;
		color: #5e7282;
		text-align: right;
	}

	/* ── Plain chart legend (footnote) ── */
	.chart-legend {
		display: flex;
		flex-wrap: wrap;
		gap: 16px;
		margin-top: 10px;
		padding-left: 4px;
	}
	.lg {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-size: 11px;
		color: #8a9baa;
	}
	.lg-line {
		width: 16px;
		height: 3px;
		border-radius: 2px;
	}
	.lg-band {
		width: 16px;
		height: 11px;
		border-radius: 2px;
		border: 1px dashed;
	}
	.lg-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		display: inline-block;
	}

	/* ── Instant timeline tooltip ── */
	.day-tooltip {
		position: fixed;
		transform: translate(-50%, -150%);
		background: #1a2530;
		border: 1px solid rgba(255,255,255,0.1);
		color: #d9e5ec;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		padding: 3px 7px;
		border-radius: 4px;
		pointer-events: none;
		white-space: nowrap;
		z-index: 100;
	}

	/* ── Responsive ── */
	@media (max-width: 768px) {
		.stat-bar { grid-template-columns: repeat(2, 1fr); }
		.day-nav { flex-direction: column; align-items: stretch; }
		.two-col-row { flex-direction: column; }
	}
</style>
