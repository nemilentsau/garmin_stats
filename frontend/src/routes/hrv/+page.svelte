<script lang="ts">
	import { onMount, tick } from 'svelte';
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
	import { garminStatusKey } from '$lib/hrv-status';
	import LineChart from '$lib/components/LineChart.svelte';
	import BarChart from '$lib/components/BarChart.svelte';
	import { fmt, fmtSigned } from '$lib/format';
	import { errorMessage } from '$lib/errors';
	import { historicalApplyOptions } from '$lib/hrv-async';
	import { fmtFullDate, parseIsoDate } from '$lib/date';
	import { COLORS, withAlpha, insightLevelColor } from '$lib/colors';
	import { chartTooltip, DARK_GRID, DARK_GRID_Y, DARK_BORDER, DARK_TICK } from '$lib/chart-setup';
	import TrendRangePicker from '$lib/components/TrendRangePicker.svelte';
	import BaselineWindowPicker from '$lib/components/BaselineWindowPicker.svelte';
	import { type TrendRange, filterByRange, PERIOD_KEY_MAP } from '$lib/trend-range';
	import type { ChartConfiguration } from 'chart.js';
	import { tightScale } from '$lib/chart-scale';

	// ── State ──
	let agg: HrvDaily | null = $state(null);
	let analysis: HrvAnalysis | null = $state(null);
	// Day-of-week pattern windows are baseline-independent — the backend returns identical data for
	// every window. Holding them in their own state (updated only when the content actually changes)
	// lets a baseline switch replace the nightly trend without handing the weekday chart a new object
	// reference, so toggling 30/60/90 never rebuilds and re-animates a chart whose data didn't move.
	let patternWindows = $state<HrvAnalysis['pattern_windows'] | null>(null);
	let dashOverview: DashboardOverview | null = $state(null);
	let loading = $state(true);
	let error: string | null = $state(null);
	// Non-blocking errors scoped to a failed secondary fetch, kept separate from `error`
	// so one failed sub-request never blanks the already-loaded dashboard. `detailError`
	// covers the selected-night fetch (rendered in the night-detail panel); `baselineError`
	// covers a baseline-window switch (rendered by the trend hero, which is always visible
	// when data is loaded, so the failure is surfaced even with no night open).
	let detailError = $state<string | null>(null);
	let baselineError = $state<string | null>(null);

	// Latest day (Tier 1 — always the most recent)
	let latestInsights: HrvInsights | null = $state(null);

	// Historical day (Tier 2 — selected via strip). The detail panel is open exactly when a night
	// is selected, so `historyOpen` is derived, not a second flag kept in lockstep with selectedDate.
	let selectedDate = $state('');
	let historyOpen = $derived(selectedDate !== '');
	let dayHover: { date: string; x: number; y: number } | null = $state(null);
	let historicalInsights: HrvInsights | null = $state(null);
	let dayStripContainer: HTMLDivElement | null = $state(null);
	let timelineHasAutoScrolled = false;
	// Two independent request tokens for two ORTHOGONAL concerns, so neither cancels the other:
	//   • windowReq — the chart/window snapshot (analysis, headline, committed baseline window).
	//     Bumped by the initial/SSE load (fetchData) and a baseline-window switch (onBaselineChange).
	//   • detailReq — the selected-night detail panel. Bumped by night selection (onDateChange).
	// A night click must not cancel an in-flight baseline switch (or vice-versa): they write
	// disjoint state, so they carry disjoint tokens. The snapshot path still applies the open
	// night's refresh only when that night is still selected (historicalApplyOptions), so a window
	// load can never clobber a fresher night selection even though they run concurrently.
	let windowReq = 0;
	let detailReq = 0;
	// Token (a windowReq value) of the most recent baseline switch. The spinner and optimistic
	// picker highlight are owned by exactly one switch at a time: a switch clears them in its
	// `finally` only if it is still the latest (`baselineReq === myReq`), so a superseding SSE
	// refresh can't leave the spinner stuck while a newer switch keeps them for itself.
	let baselineReq = 0;
	// Optimistic window for the picker highlight ONLY, set the moment a switch starts so the
	// clicked button lights up immediately. The committed window (`baselineWindow`) still moves
	// only when the chart data applies, so this never feeds the legend, URL, or any fetch.
	let pendingBaseline = $state<HrvBaselineWindow | null>(null);
	// A baseline switch is in flight exactly while it holds the optimistic highlight, so the
	// spinner/disabled state is simply derived from pendingBaseline — one source of truth, no
	// second flag to keep in lockstep.
	let baselineLoading = $derived(pendingBaseline !== null);

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
		// Error from the isolated selected-night sub-fetch (null on success). Carried on the
		// snapshot instead of thrown so a failed night fetch can't abort the chart/headline.
		historicalError: string | null;
		baseline: HrvBaselineWindow;
	};

	// ── Data fetching ──
	async function loadHrvSnapshot(
		window: HrvBaselineWindow,
		historicalDate = '',
		// getHrvDaily and getDashboardOverview don't vary with the baseline window. On a
		// baseline switch the caller passes the already-loaded copies via `reuse` so we fetch
		// only the window-dependent analysis + insights instead of re-downloading them.
		reuse?: { agg: HrvDaily; dashOverview: DashboardOverview }
	): Promise<HrvSnapshot> {
		// Kick off the window-dependent analysis immediately so it overlaps the (skippable)
		// window-independent fetches on a full load.
		const analysisP = api.getHrvAnalysis(window);
		const [nextAgg, nextOverview] = reuse
			? [reuse.agg, reuse.dashOverview]
			: await Promise.all([api.getHrvDaily(), api.getDashboardOverview()]);
		const latest = nextAgg.days[nextAgg.days.length - 1] ?? '';
		// The insights depend only on the (now-known) agg + window, NOT on the analysis, so fetch
		// them in parallel with analysisP — a baseline switch is then one round trip, not two.
		const latestP = latest ? api.getHrvInsights(latest, window) : Promise.resolve(null);
		// The selected-night insights are a secondary, ISOLATED sub-fetch: its failure must not
		// reject the snapshot (which on an SSE refresh would blank the already-loaded chart +
		// headline). Capture any error and let applyHrvSnapshot surface it in the night panel
		// via detailError, exactly as the click path (onDateChange) does. The latest-night
		// insights stay a hard dependency — they drive the always-visible headline.
		// When the open night IS the latest night (the common default focus), reuse the latest
		// insights request instead of firing a second byte-identical GET — same date, same window.
		const historicalReq =
			historicalDate === latest ? latestP : api.getHrvInsights(historicalDate, window);
		const historicalP: Promise<{ insights: HrvInsights | null; error: string | null }> =
			historicalDate
				? historicalReq
						.then((insights) => ({ insights, error: null }))
						.catch((e: unknown) => ({
							insights: null,
							error: e instanceof Error ? e.message : String(e)
						}))
				: Promise.resolve({ insights: null, error: null });
		const [nextAnalysis, nextLatestInsights, historical] = await Promise.all([
			analysisP,
			latestP,
			historicalP
		]);
		return {
			agg: nextAgg,
			analysis: nextAnalysis,
			dashOverview: nextOverview,
			latestInsights: nextLatestInsights,
			historicalInsights: historical.insights,
			historicalError: historical.error,
			baseline: window
		};
	}

	function applyHrvSnapshot(
		snapshot: HrvSnapshot,
		options: { applyHistorical?: boolean; clearDetailError?: boolean } = {}
	) {
		agg = snapshot.agg;
		analysis = snapshot.analysis;
		// Refresh the baseline-independent weekday windows only when their content changed (e.g. an
		// SSE re-ingest), so a mere baseline switch leaves the reference — and the weekday chart —
		// untouched. The dict is tiny (3 windows × 7 weekdays), so the equality check is cheap.
		const nextPatterns = snapshot.analysis.pattern_windows;
		if (!patternWindows || JSON.stringify(nextPatterns) !== JSON.stringify(patternWindows)) {
			patternWindows = nextPatterns;
		}
		dashOverview = snapshot.dashOverview;
		latestInsights = snapshot.latestInsights;
		// The rendered window commits HERE, atomically with the chart data it describes — never
		// eagerly in onBaselineChange. That keeps the picker, legend, URL, chart band and panel
		// z from ever disagreeing on the window: a superseded baseline switch simply never
		// applies, leaving every surface on the previously-rendered window.
		baselineWindow = snapshot.baseline;
		if (options.applyHistorical) {
			// Selected-night sub-fetch is isolated: on failure the panel shows detailError (and
			// blanks, never showing a wrong-window z), without aborting this chart/headline apply.
			historicalInsights = snapshot.historicalInsights;
			detailError = snapshot.historicalError;
		} else if (options.clearDetailError ?? true) {
			detailError = null;
		}
		// A successful load supersedes any prior top-level and baseline errors.
		error = null;
		baselineError = null;
		void scrollTimelineToLatestOnce();
	}

	async function scrollTimelineToLatestOnce() {
		if (timelineHasAutoScrolled) return;
		await tick();
		if (!dayStripContainer) return;
		dayStripContainer.scrollLeft = dayStripContainer.scrollWidth;
		timelineHasAutoScrolled = true;
	}

	async function fetchData() {
		const myReq = ++windowReq;
		// An in-flight baseline switch is newer user intent than this background/SSE refresh, so
		// adopt its target window: this refresh bumps windowReq and so supersedes the switch, and
		// without adoption a `data_updated` event landing mid-switch would drop the user's click and
		// snap the picker back to the old window. Adopting commits the selection on this refresh.
		const adoptedBaseline = pendingBaseline;
		const requestedBaseline = adoptedBaseline ?? baselineWindow;
		// Refresh the open night's detail alongside the chart: an SSE-triggered reload must
		// not move the chart's bands/markers while leaving the panel's z-score stale, since
		// the chart and the panel must agree for a given night + window.
		const historicalDate = selectedDate;
		const snapshot = await loadHrvSnapshot(requestedBaseline, historicalDate);
		if (myReq !== windowReq) return;
		applyHrvSnapshot(snapshot, historicalApplyOptions(historicalDate, selectedDate));
		// If this refresh adopted a pending switch's window, persist it so the URL matches the
		// now-committed window (the superseded switch never reaches its own setBaselineUrl).
		if (adoptedBaseline !== null) setBaselineUrl(adoptedBaseline);
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
			// Bump the detail token so any night fetch still in flight is discarded
			// rather than repopulating the panel after it closes.
			++detailReq;
			selectedDate = '';
			historicalInsights = null;
			detailError = null;
			return;
		}
		selectedDate = date;
		historicalInsights = null;
		detailError = null;
		const myReq = ++detailReq;
		// Fetch at the window currently in effect — or the one a baseline switch is mid-flight to
		// (pendingBaseline) — so a night opened during a switch lands on the same window the chart
		// commits to, keeping this panel's z and the chart band in agreement for the night.
		const baseline = pendingBaseline ?? baselineWindow;
		try {
			const nextInsights = await api.getHrvInsights(date, baseline);
			if (myReq !== detailReq) return;
			historicalInsights = nextInsights;
			detailError = null;
		} catch (e: unknown) {
			if (myReq !== detailReq) return;
			detailError = errorMessage(e);
		}
	}

	function setBaselineUrl(w: HrvBaselineWindow) {
		const url = new URL(window.location.href);
		url.searchParams.set('baseline', String(w));
		replaceState(url, {});
	}

	async function onBaselineChange(w: HrvBaselineWindow) {
		const selectedForBaseline = selectedDate;
		const myReq = ++windowReq;
		baselineReq = myReq;
		// Optimistic highlight only — the window itself does NOT move until the data applies.
		// pendingBaseline also drives the derived baselineLoading (spinner + disabled picker).
		pendingBaseline = w;
		baselineError = null;
		try {
			// The baseline knob only changes window-dependent data — reuse the loaded daily
			// aggregate and dashboard overview instead of re-fetching them.
			const reuse = agg && dashOverview ? { agg, dashOverview } : undefined;
			const snapshot = await loadHrvSnapshot(w, selectedForBaseline, reuse);
			if (myReq !== windowReq) return;
			// Commit window + chart + URL together. A night click does NOT bump windowReq, so it can
			// never supersede this switch (the bug where inspecting a night reverted the window); a
			// newer window load (another switch / SSE refresh) does, and then we never reach here, so
			// the window/URL stay on the rendered window — chart band and panel z can't split.
			applyHrvSnapshot(snapshot, historicalApplyOptions(selectedForBaseline, selectedDate));
			setBaselineUrl(w);
		} catch (e: unknown) {
			if (myReq !== windowReq) return;
			// The window was never moved, so there is nothing to roll back — just surface a
			// non-blocking error; the dashboard keeps showing the window still on screen.
			baselineError = `Couldn't load the ${w}-day baseline — still showing ${baselineWindow}-day. ${errorMessage(e)}`;
		} finally {
			// Clear the optimistic highlight (which also clears the derived spinner) only if we are
			// still the latest baseline switch. A newer switch (baselineReq moved) owns it now;
			// otherwise clear it whether we won, errored, or were superseded — so the spinner never
			// sticks and the picker falls back to the window actually on screen.
			if (baselineReq === myReq) {
				pendingBaseline = null;
			}
		}
	}

	function closeHistory() {
		// Identical to selecting "no night" — delegate so the close/reset semantics live in one
		// place (onDateChange's empty-date branch cancels any in-flight night fetch too).
		void onDateChange('');
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
	// Single source for HRV status colors, following the app's good→caution→warning
	// convention (see insightLevelColor) so a palette change flows from one place.
	const HRV_STATUS_COLORS: Record<string, string> = {
		Balanced: COLORS.heartRateResting, // good — green
		Unbalanced: COLORS.stress,         // caution — amber
		Low: COLORS.heartRate,             // warning — red
		High: COLORS.respiration           // above normal — teal
	};
	const UNKNOWN_STATUS_COLOR = '#3a4a5a';

	// ── History strip colors: by the AVERAGED TREND (ma7 vs typical-range band), not
	// per-night status — a single night is noise. trend_state comes from the backend. ──
	// One map is the single source of truth for BOTH the color and the label of each trend
	// state, so the strip cell and the legend can never disagree on (or drift apart in) the set
	// of states. Three clearly-distinct hues for the low→normal→high trend (amber / green / blue).
	const TREND_STATES: Record<string, { color: string; label: string }> = {
		below: { color: COLORS.stress, label: 'Below typical' },             // amber
		within: { color: COLORS.heartRateResting, label: 'Within typical' }, // green
		above: { color: COLORS.spo2, label: 'Above typical' }                // blue
	};

	// One pass over the densified trend builds BOTH the date→color map and the legend (these used
	// to walk the series twice). The legend lists the trend states actually present, in palette
	// order, plus a gray "Building baseline" entry when any day lacks a trend (the warmup weeks
	// before a typical-range band exists) so gray reads as a labelled state, not a mystery.
	let strip = $derived.by(() => {
		const map = new Map<string, string>();
		const present = new Set<string>();
		let hasUnclassified = false;
		for (const p of analysis?.nightly_trend ?? []) {
			const state = p.trend_state;
			map.set(p.date, (state && TREND_STATES[state]?.color) || UNKNOWN_STATUS_COLOR);
			if (state) present.add(state);
			else hasUnclassified = true;
		}
		const legend = Object.keys(TREND_STATES)
			.filter((s) => present.has(s))
			.map((s) => ({ label: TREND_STATES[s].label, color: TREND_STATES[s].color }));
		if (hasUnclassified) {
			legend.push({ label: 'Building baseline', color: UNKNOWN_STATUS_COLOR });
		}
		return { map, legend };
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
	// Only the tooltip is reused: the trend chart hides Chart.js's built-in legend
	// (`legend: { display: false }` below) in favor of the hand-rolled HTML legend under the
	// chart, so a legend style object here would never render.
	const darkPlugins = {
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
		// Shared range filter (same cutoff + `date >= cutoff` as every other metric tab), so a
		// future change to range semantics flows here too instead of skipping the HRV chart.
		const t = filterByRange(analysis.nightly_trend, trendRange);
		const labels = t.map((p) => p.date);
		// Map each plotted series once and reuse it for both the dataset and the y-scale, so the
		// scale inputs can't drift from what's drawn and we don't pass over the series twice.
		const ma7 = t.map((p) => p.ma7);
		const bandLow = t.map((p) => p.band_low);
		const bandHigh = t.map((p) => p.band_high);
		const datasets: ChartConfiguration<'line'>['data']['datasets'] = [
			{
				label: 'Band Low',
				data: bandLow,
				borderColor: withAlpha(COLORS.hrvWeekly, '30'),
				borderWidth: 1, pointRadius: 0, tension: 0.3, spanGaps: false, fill: false
			},
			{
				label: 'Band High',
				data: bandHigh,
				borderColor: withAlpha(COLORS.hrvWeekly, '30'),
				borderWidth: 1, pointRadius: 0, tension: 0.3, spanGaps: false,
				fill: '-1', backgroundColor: withAlpha(COLORS.hrvWeekly, '14')
			},
			{
				label: '7-Day MA',
				data: ma7,
				// spanGaps:false so the trend breaks at no-reading nights (the backend emits null
				// points for them) instead of bridging a straight segment over missing data.
				borderColor: COLORS.hrv, borderWidth: 2.5, pointRadius: 0, tension: 0.3, spanGaps: false
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

		const yScale = tightScale([...ma7, ...bandLow, ...bandHigh], 2, 5);

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
	// Reads the separately-held, baseline-independent `patternWindows` (not `analysis`) so a
	// baseline switch doesn't hand this — and the weekday chart below — a new object reference.
	let patternWindow = $derived.by(() => {
		const key = PERIOD_KEY_MAP[trendRange];
		return patternWindows?.[key] ?? null;
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

	// Bar opacity per backend-computed weekday state — the frontend maps a backend value to a
	// shade and does NO value-vs-reference classification of its own (that ±5 ms policy lives in
	// the backend; see docs/reference/hrv.md "Trend versus one night"). Missing state → neutral.
	const DAY_OF_WEEK_STATE_ALPHA: Record<string, string> = {
		above: 'cc', // brightest — weekday runs above the grand mean
		within: '77',
		below: '33' // dimmest — runs below
	};

	let dayOfWeekConfig = $derived.by<ChartConfiguration<'bar'> | null>(() => {
		if (dayOfWeek.length === 0) return null;
		return {
			type: 'bar',
			data: {
				labels: dayOfWeek.map((b) => b.day),
				datasets: [
					{
						label: 'Avg Nightly HRV',
						data: dayOfWeek.map((b) => b.avg_nightly),
						backgroundColor: dayOfWeek.map((b) =>
							withAlpha(COLORS.hrv, (b.state && DAY_OF_WEEK_STATE_ALPHA[b.state]) || '55')
						),
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

{#snippet garminChip(status: string | null | undefined)}
	{@const key = garminStatusKey(status)}
	{#if key}
		<span class="garmin-chip" title="Garmin's own multi-day HRV status — a separate signal from tonight's recovery">
			<i class="garmin-dot" style="background: {HRV_STATUS_COLORS[key] ?? UNKNOWN_STATUS_COLOR};"></i>
			Garmin: {key}
		</span>
	{/if}
{/snippet}

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
				<!-- Neutral, non-verdict color: the delta is a single-night vs trailing-7d number
				     (a "today" signal). Recovery state lives in the insight line below; Garmin's
				     multi-day status is its own separate chip — neither is folded in here. -->
				<span class="stat-delta">
					{fmtSigned(latestRecovery.delta_nightly_from_baseline)} vs {fmt(latestRecovery.baseline_nightly_7d)} avg
				</span>
			{/if}
		</div>
	</div>

	{@render garminChip(latestDayStats?.status)}

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
						<BaselineWindowPicker value={pendingBaseline ?? baselineWindow} onchange={onBaselineChange} disabled={baselineLoading} />
					</div>
					<span class="control-sep" aria-hidden="true"></span>
					<div class="control-group">
						<span class="control-label">Show</span>
						<TrendRangePicker bind:value={trendRange} />
					</div>
				</div>
			</div>
			{#if baselineError}
				<div class="detail-error">{baselineError}</div>
			{/if}
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
		<div class="day-strip-container" bind:this={dayStripContainer}>
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
						style="background: {strip.map.get(day) ?? UNKNOWN_STATUS_COLOR};"
						aria-label={day}
						onmouseenter={(e) => showDayHover(e, day)}
						onclick={() => onDateChange(day === selectedDate ? '' : day)}
					></button>
				{/each}
			</div>
			<div class="month-axis" aria-hidden="true">
				{#each monthSegments as seg}
					<span class="month-tick" style="--days: {seg.count};">{seg.label}</span>
				{/each}
			</div>
			<div class="day-strip-legend">
				{#each strip.legend as { label, color }}
					<span><i class="legend-dot" style="background:{color};"></i>{label}</span>
				{/each}
			</div>
		</div>
	</div>

	{#if dayHover}
		<div class="day-tooltip" style="left: {dayHover.x}px; top: {dayHover.y}px;">{dayHover.date}</div>
	{/if}

	<!-- Expandable night detail (open exactly when a night is selected) -->
	{#if historyOpen}
		<div class="history-detail" transition:slide={{ duration: 300 }}>
			<div class="history-detail-header">
				<div class="history-detail-title">
					<span class="history-date">{selectedDate}</span>
					{@render garminChip(historicalDayStats?.status)}
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
						<!-- 2 decimals to match the backend: z is authored at 2dp and the "extreme night"
						     flag is derived from that same value (|z| > 2.0), so showing 1dp could render
						     "+2.0 SD · extreme night" where the number doesn't exceed the threshold. -->
						<strong>{fmtSigned(historicalInsights.baseline.selected_z, 2)} SD</strong>
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
				<p class="card-footnote">{patternWindow?.total_sample_count ?? 0} total nights ({patternWindowLabel}) · weekday averages, not single-night predictions</p>
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
						<span class="comove-r">{fmtSigned(corr.r_value, 2)}</span>
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
		grid-template-columns: minmax(0, 1fr);
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
		color: #6b7d8e;
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
		/* One source for the day-cell stride: the timeline cells and the month axis below it must
		   advance by the same width + gap, or the month labels drift off the cells they mark. */
		--day-cell-w: 8px;
		--day-strip-gap: 2px;
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
		overflow-x: auto;
		overflow-y: visible;
		scrollbar-width: thin;
		scrollbar-color: rgba(255,255,255,0.18) transparent;
	}
	.day-strip {
		display: flex;
		gap: var(--day-strip-gap);
		padding: 2px 0;
		width: max-content;
	}
	.day-strip-container::-webkit-scrollbar { height: 6px; }
	.day-strip-container::-webkit-scrollbar-thumb {
		background: rgba(255,255,255,0.18);
		border-radius: 999px;
	}
	.day-strip-container::-webkit-scrollbar-track { background: transparent; }

	.day-cell {
		flex: 0 0 var(--day-cell-w);
		min-width: var(--day-cell-w);
		height: 28px;
		border-radius: 2px;
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
		/* Pinned to the left of the horizontally-scrolling strip so the key stays visible
		   no matter how far the timeline is scrolled. */
		position: sticky;
		left: 0;
		width: fit-content;
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
		width: max-content;
	}
	.month-tick {
		/* Stride per day = cell width + inter-cell gap, derived from the same vars the strip uses
		   so the month axis always stays aligned with the day cells above it. */
		flex: 0 0 calc(var(--days) * (var(--day-cell-w) + var(--day-strip-gap)));
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

	/* ── Garmin status chip ── */
	.garmin-chip {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		text-transform: uppercase;
		letter-spacing: 1px;
		color: #8a9baa;
	}
	.garmin-dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		display: inline-block;
	}

	/* ── Responsive ── */
	@media (max-width: 768px) {
		.stat-bar { grid-template-columns: minmax(0, 1fr); }
		.day-nav { flex-direction: column; align-items: stretch; }
		.two-col-row { flex-direction: column; }
	}
</style>
