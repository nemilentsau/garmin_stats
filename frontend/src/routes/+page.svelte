<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type DailyAggregates, type DashboardOverview, type IngestStatus } from '$lib/api';
	import { startRealtimePage } from '$lib/realtime-page';
	import { Chart, DARK_BORDER, DARK_GRID_Y, DARK_TICK, chartTooltip } from '$lib/chart-setup';
	import type { ChartConfiguration } from 'chart.js';
	import { fmt, fmtSigned } from '$lib/format';
	import { COLORS } from '$lib/colors';
	import { calendarDayDiff, localDateIso, parseIsoDate } from '$lib/date';

	let data: DailyAggregates | null = $state(null);
	let overview: DashboardOverview | null = $state(null);
	let ingestStatus: IngestStatus | null = $state(null);
	let emptyState: IngestStatus | null = $state(null);
	let error: string | null = $state(null);
	let sparkCanvases: Record<string, HTMLCanvasElement> = $state({});
	let sparkCharts: Record<string, Chart<'line'>> = {};

	const bannerDateFormat = new Intl.DateTimeFormat('en-US', {
		month: 'short',
		day: 'numeric',
		year: 'numeric'
	});

	async function fetchData() {
		error = null;
		const status = await api.getIngestStatus();
		ingestStatus = status;
		if (status.days_in_db === 0) {
			data = null;
			overview = null;
			emptyState = status;
			return;
		}

		const [nextData, nextOverview] = await Promise.all([
			api.getDailyAggregates(),
			api.getDashboardOverview()
		]);
		data = nextData;
		overview = nextOverview;
		emptyState = null;
	}

	function formatBannerDate(date: string): string {
		return bannerDateFormat.format(parseIsoDate(date));
	}

	onMount(() => {
		return startRealtimePage({
			fetchData,
			setError: (message) => { error = message; },
			setLoading: () => {}
		});
	});

	const latestIngestedDate = $derived.by(() => data?.days[data.days.length - 1] ?? null);

	const freshnessNotice = $derived.by(() => {
		if (!ingestStatus || ingestStatus.days_in_db === 0 || !latestIngestedDate) return null;

		const today = localDateIso();
		const daysBehind = calendarDayDiff(latestIngestedDate, today);
		if (daysBehind > 0) {
			return {
				tone: 'stale' as const,
				headline: `Garmin data is ${daysBehind} ${daysBehind === 1 ? 'day' : 'days'} behind the laptop date.`,
				detail: `Data is current through ${formatBannerDate(latestIngestedDate)}. This laptop is on ${formatBannerDate(today)}. Update exports before trusting current-day planning or experiment context.`
			};
		}

		if (ingestStatus.needs_ingest) {
			return {
				tone: 'pending' as const,
				headline: 'New Garmin files are waiting to ingest.',
				detail: `Current data is through ${formatBannerDate(latestIngestedDate)}. Run an ingest after the next device sync if you need the newest recovery signals.`
			};
		}

		return null;
	});

	function readinessColor(score: number | null | undefined): string {
		if (score == null) return '#8a9baa';
		if (score >= 75) return COLORS.heartRateResting;
		if (score >= 50) return COLORS.stress;
		return COLORS.heartRate;
	}

	type ReadinessComponent = {
		label: string;
		color: string;
		description: string;
	};

	const componentInfo: Record<string, ReadinessComponent> = {
		hrv_recovery: {
			label: 'HRV Recovery',
			color: COLORS.hrv,
			description: 'Overnight HRV trend vs your recent baseline'
		},
		sleep: {
			label: 'Sleep',
			color: COLORS.sleep,
			description: 'Sleep quality score from last night'
		},
		resting_hr: {
			label: 'Resting HR',
			color: COLORS.heartRate,
			description: 'Resting heart rate change vs 7-day average'
		},
		hrv_status: {
			label: 'HRV Status',
			color: COLORS.respiration,
			description: 'Autonomic nervous system balance assessment'
		}
	};

	const componentOrder = ['hrv_recovery', 'sleep', 'resting_hr', 'hrv_status'] as const;

	// ── Combined metric card config (vitals + sparklines) ──
	type SparkSeries = NonNullable<DashboardOverview['sparklines']>['resting_hr'];

	type MetricCardConfig = {
		key: string;
		label: string;
		unit: string;
		color: string;
		getValue: (v: NonNullable<DashboardOverview['vitals']>) => number | null | undefined;
		getDelta: (v: NonNullable<DashboardOverview['vitals']>) => number | null | undefined;
		lowerIsBetter: boolean;
		getSeries: (s: NonNullable<DashboardOverview['sparklines']>) => SparkSeries;
	};

	const metricConfigs: MetricCardConfig[] = [
		{
			key: 'resting_hr',
			label: 'Resting HR',
			unit: 'bpm',
			color: COLORS.heartRate,
			getValue: (v) => v.resting_hr,
			getDelta: (v) => v.resting_hr_delta_7d,
			lowerIsBetter: true,
			getSeries: (s) => s.resting_hr
		},
		{
			key: 'nightly_hrv',
			label: 'Nightly HRV',
			unit: 'ms',
			color: COLORS.hrv,
			getValue: (v) => v.nightly_hrv,
			getDelta: (v) => v.nightly_hrv_delta_7d,
			lowerIsBetter: false,
			getSeries: (s) => s.nightly_hrv
		},
		{
			key: 'sleep_score',
			label: 'Sleep Score',
			unit: 'pts',
			color: COLORS.sleep,
			getValue: (v) => v.sleep_score,
			getDelta: () => null,
			lowerIsBetter: false,
			getSeries: (s) => s.sleep_score
		},
		{
			key: 'stress_avg',
			label: 'Stress',
			unit: 'avg',
			color: COLORS.stress,
			getValue: (v) => v.stress_avg,
			getDelta: () => null,
			lowerIsBetter: true,
			getSeries: (s) => s.stress_avg
		}
	];

	function deltaColor(delta: number | null | undefined, lowerIsBetter: boolean): string {
		if (delta == null) return '#5e7282';
		const isGood = lowerIsBetter ? delta < 0 : delta > 0;
		if (isGood) return COLORS.heartRateResting;
		if (delta === 0) return '#5e7282';
		return COLORS.heartRate;
	}

	// ── Sparkline chart creation ──
	function sparkDateLabels(points: Array<{ date: string }>): string[] {
		const len = points.length;
		if (len === 0) return [];
		// Show ~4 evenly spaced date labels, avoiding overlap at the end
		const step = Math.max(1, Math.floor(len / 4));
		const minGap = Math.floor(step * 0.6); // don't show last label if too close to previous
		let lastShown = -Infinity;
		return points.map((p, i) => {
			const isFirst = i === 0;
			const isLast = i === len - 1;
			const isStep = i % step === 0;
			if (isFirst || isStep) {
				lastShown = i;
				return p.date.slice(5); // MM-DD
			}
			if (isLast && (i - lastShown) >= minGap) {
				return p.date.slice(5);
			}
			return '';
		});
	}

	function createSparkline(canvas: HTMLCanvasElement, points: Array<{ date: string; value: number | null; ma7: number | null }>, color: string): Chart<'line'> {
		const ma7Vals = points.map(p => p.ma7).filter((v): v is number => v != null);
		const dataMin = ma7Vals.length ? Math.min(...ma7Vals) : 0;
		const dataMax = ma7Vals.length ? Math.max(...ma7Vals) : 100;
		const range = dataMax - dataMin || 1;
		const padding = range * 0.1;

		const config: ChartConfiguration<'line'> = {
			type: 'line',
			data: {
				labels: sparkDateLabels(points),
				datasets: [
					// 7-day moving average only
					{
						data: points.map((p) => p.ma7),
						borderColor: color,
						backgroundColor: color + '12',
						borderWidth: 2,
						pointRadius: 0,
						pointHoverRadius: 4,
						pointHoverBackgroundColor: color,
						pointHoverBorderColor: '#0d1520',
						pointHoverBorderWidth: 2,
						tension: 0.35,
						spanGaps: true,
						fill: true
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				interaction: {
					mode: 'index',
					intersect: false
				},
				plugins: {
					legend: { display: false },
					tooltip: {
						enabled: true,
						...chartTooltip(color),
						titleFont: { family: 'DM Mono', size: 10 },
						bodyFont: { family: 'DM Mono', size: 12, weight: 'bold' },
						titleColor: '#8a9baa',
						bodyColor: color,
						displayColors: false,
						callbacks: {
							title: function(items) {
								if (!items.length) return '';
								const idx = items[0].dataIndex;
								return points[idx]?.date ?? '';
							},
							label: function(item) {
								const v = item.parsed.y;
								return v != null ? '7d avg: ' + fmt(v) : '-';
							}
						}
					}
				},
				scales: {
					x: {
						display: true,
						border: DARK_BORDER,
						grid: { display: false },
						ticks: {
							color: '#6b7d8e',
							font: { family: 'DM Mono', size: 10 },
							maxRotation: 0,
							autoSkip: false,
							callback: function(_value: string | number, index: number) {
								const labels = this.chart.data.labels as string[];
								return labels[index] || null;
							}
						}
					},
					y: {
						display: true,
						border: { display: false },
						grid: DARK_GRID_Y,
						min: dataMin - padding,
						max: dataMax + padding,
						ticks: {
							...DARK_TICK,
							font: { family: 'DM Mono', size: 10 },
							maxTicksLimit: 4,
							callback: function(value) {
								return Math.round(Number(value));
							}
						}
					}
				},
				animation: false
			}
		};
		return new Chart(canvas, config);
	}

	$effect(() => {
		if (!overview?.sparklines) return;
		const sparklines = overview.sparklines;
		for (const mc of metricConfigs) {
			const canvas = sparkCanvases[mc.key];
			if (!canvas) continue;
			const series = mc.getSeries(sparklines);
			const points = series.points;
			const existing = sparkCharts[mc.key];
			if (existing) {
				// Update data and Y-axis range in-place
				const ma7Vals = points.map(p => p.ma7).filter((v): v is number => v != null);
				const dataMin = ma7Vals.length ? Math.min(...ma7Vals) : 0;
				const dataMax = ma7Vals.length ? Math.max(...ma7Vals) : 100;
				const range = dataMax - dataMin || 1;
				const padding = range * 0.1;
				existing.data.labels = sparkDateLabels(points);
				existing.data.datasets[0].data = points.map(p => p.ma7);
				existing.options.scales!.y!.min = dataMin - padding;
				existing.options.scales!.y!.max = dataMax + padding;
				existing.update();
			} else {
				sparkCharts[mc.key] = createSparkline(canvas, points, mc.color);
			}
		}
	});

	onMount(() => {
		return () => {
			Object.values(sparkCharts).forEach((c) => c.destroy());
		};
	});
</script>

<svelte:head>
	<title>Dashboard - Garmin Stats</title>
</svelte:head>

{#if error}
	<div class="topo-error">
		<p>Error: {error}</p>
	</div>
{:else if emptyState}
	<section class="empty-shell">
		<div class="empty-welcome">
			<div class="empty-icon">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
					<path d="M22 12h-4l-3 9L9 3l-3 9H2" />
				</svg>
			</div>
			<div class="empty-text">
				<h2>Waiting for Garmin data</h2>
				<p>
					{#if emptyState.days_on_disk === 0}
						Drop <code>.zip</code> archives into <code>data/garmin_health_stats/</code> to get started.
					{:else}
						{emptyState.days_on_disk} {emptyState.days_on_disk === 1 ? 'day' : 'days'} found on disk — trigger an ingest to build the dashboard.
					{/if}
				</p>
			</div>
		</div>

		<div class="empty-steps">
			<div class="empty-step" class:done={emptyState.days_on_disk > 0}>
				<div class="step-marker">{emptyState.days_on_disk > 0 ? '✓' : '1'}</div>
				<div class="step-body">
					<span class="step-title">Add export archives</span>
					<span class="step-desc">Place Garmin <code>YYYY-MM-DD.zip</code> files in the data directory</span>
				</div>
			</div>
			<div class="step-connector"></div>
			<div class="empty-step">
				<div class="step-marker">2</div>
				<div class="step-body">
					<span class="step-title">Ingest</span>
					<span class="step-desc">POST to <code>/api/ingest</code> or wait for the watcher to pick them up</span>
				</div>
			</div>
			<div class="step-connector"></div>
			<div class="empty-step">
				<div class="step-marker">3</div>
				<div class="step-body">
					<span class="step-title">Dashboard populates</span>
					<span class="step-desc">Recovery scores, vitals, and trends appear automatically</span>
				</div>
			</div>
		</div>
	</section>
{:else if !data}
	<div class="topo-loading">
		<div class="loading-pulse"></div>
		<span>Mapping terrain data...</span>
	</div>
{:else}
	{#if freshnessNotice}
		<section class:pending={freshnessNotice.tone === 'pending'} class="freshness-banner">
			<div class="freshness-label">Data freshness</div>
			<div class="freshness-copy">
				<strong>{freshnessNotice.headline}</strong>
				<p>{freshnessNotice.detail}</p>
			</div>
		</section>
	{/if}

	<!-- Readiness hero -->
	{#if overview?.readiness}
		{@const r = overview.readiness}
		<div class="readiness-hero">
			<div class="readiness-top">
				<div class="readiness-ring" style="--ring-color:{readinessColor(r.score)}; --ring-pct:{r.score ?? 0}">
					<svg viewBox="0 0 120 120" class="ring-svg">
						<circle cx="60" cy="60" r="52" class="ring-track" />
						<circle cx="60" cy="60" r="52" class="ring-fill" style="stroke:{readinessColor(r.score)}; stroke-dasharray:{((r.score ?? 0) / 100) * 327} 327" />
					</svg>
					<div class="ring-content">
						<span class="ring-score" style="color:{readinessColor(r.score)}">{r.score ?? '-'}</span>
					</div>
				</div>
				<div class="readiness-info">
					<span class="readiness-label" style="color:{readinessColor(r.score)}">{r.label ?? '-'}</span>
					<span class="readiness-subtitle">Readiness · {overview.date}</span>
					<p class="readiness-explain">
						Composite score from 4 recovery signals, each contributing up to 25 points.
					</p>
				</div>
			</div>
			<div class="readiness-components">
				{#each componentOrder as key}
					{@const val = r.components[key] ?? 0}
					{@const info = componentInfo[key]}
					{@const vitals = overview?.vitals}
					<div class="comp-row">
						<div class="comp-header">
							<div class="comp-dot" style="background:{info.color}"></div>
							<span class="comp-label">{info.label}</span>
							{#if key === 'hrv_recovery' && vitals?.nightly_hrv != null}
								<span class="comp-actual">{fmt(vitals.nightly_hrv)} ms</span>
								{#if vitals.nightly_hrv_delta_7d != null}
									<span class="comp-delta" style="color:{deltaColor(vitals.nightly_hrv_delta_7d, false)}">{fmtSigned(vitals.nightly_hrv_delta_7d)}</span>
								{/if}
							{:else if key === 'sleep' && vitals?.sleep_score != null}
								<span class="comp-actual">{vitals.sleep_score} pts</span>
							{:else if key === 'resting_hr' && vitals?.resting_hr != null}
								<span class="comp-actual">{vitals.resting_hr} bpm</span>
								{#if vitals.resting_hr_delta_7d != null}
									<span class="comp-delta" style="color:{deltaColor(vitals.resting_hr_delta_7d, true)}">{fmtSigned(vitals.resting_hr_delta_7d)}</span>
								{/if}
							{:else if key === 'hrv_status' && vitals?.hrv_status}
								<span class="comp-actual">{vitals.hrv_status}</span>
							{/if}
							<span class="comp-score" style="color:{info.color}">{Math.round(val)}</span>
							<span class="comp-max">/ 25</span>
						</div>
						<div class="comp-bar-track">
							<div class="comp-bar-fill" style="width:{(val / 25) * 100}%; background:{info.color}"></div>
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Unified Metric Cards: value + trend chart + stats -->
	{#if overview?.vitals && overview?.sparklines}
		{@const vitals = overview.vitals}
		{@const sparklines = overview.sparklines}
		<div class="metric-grid">
			{#each metricConfigs as mc}
				{@const val = mc.getValue(vitals)}
				{@const delta = mc.getDelta(vitals)}
				{@const series = mc.getSeries(sparklines)}
				{@const summary = series.summary}
				<div class="metric-card">
					<div class="metric-card-header">
						<div class="metric-card-left">
							<span class="metric-label">{mc.label}</span>
							<div class="metric-value-row">
								<span class="metric-value" style="color:{mc.color}">{fmt(val)}</span>
								<span class="metric-unit">{mc.unit}</span>
							</div>
							{#if delta != null}
								<span class="metric-delta" style="color:{deltaColor(delta, mc.lowerIsBetter)}">{fmtSigned(delta)} vs 7d</span>
							{/if}
						</div>
						{#if summary.avg != null}
							<div class="metric-card-stats">
								<div class="mini-stat">
									<span class="mini-stat-label">90d avg</span>
									<span class="mini-stat-value" style="color:{mc.color}">{fmt(summary.avg)}</span>
								</div>
								<div class="mini-stat">
									<span class="mini-stat-label">low</span>
									<span class="mini-stat-value">{fmt(summary.min)}</span>
								</div>
								<div class="mini-stat">
									<span class="mini-stat-label">high</span>
									<span class="mini-stat-value">{fmt(summary.max)}</span>
								</div>
							</div>
						{/if}
					</div>
					<div class="metric-chart">
						<canvas bind:this={sparkCanvases[mc.key]}></canvas>
					</div>
				</div>
			{/each}
		</div>
	{/if}

{/if}

<style>
	.topo-error {
		margin: 40px 0;
		padding: 20px;
		border: 1px solid rgba(232,93,74,0.3);
		border-radius: 8px;
		background: rgba(232,93,74,0.08);
		color: #E85D4A;
		font-family: 'DM Mono', monospace;
		font-size: 13px;
	}

	.topo-loading {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 12px;
		height: 60vh;
		font-family: 'DM Mono', monospace;
		font-size: 13px;
		color: #5e7282;
	}

	.loading-pulse {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: #5BB5A6;
		animation: pulse 1.5s ease-in-out infinite;
	}

	@keyframes pulse {
		0%, 100% { opacity: 0.3; transform: scale(0.8); }
		50% { opacity: 1; transform: scale(1.2); }
	}

	.empty-shell {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 32px;
		padding: 48px 0 24px;
		max-width: 520px;
		margin: 0 auto;
	}

	.empty-welcome {
		display: flex;
		align-items: center;
		gap: 16px;
	}

	.empty-icon {
		width: 44px;
		height: 44px;
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 12px;
		background: rgba(91,181,166,0.10);
		color: #5BB5A6;
	}

	.empty-icon svg {
		width: 22px;
		height: 22px;
	}

	.empty-text h2 {
		margin: 0;
		font-size: 18px;
		font-weight: 600;
		color: #e0eaf0;
		letter-spacing: -0.01em;
	}

	.empty-text p {
		margin: 4px 0 0;
		font-size: 13px;
		color: #7e8f9e;
		line-height: 1.5;
	}

	.empty-text code {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #a0b8c8;
		background: rgba(255,255,255,0.05);
		padding: 1px 5px;
		border-radius: 4px;
	}

	.empty-steps {
		display: flex;
		flex-direction: column;
		gap: 0;
		width: 100%;
		padding: 20px 24px;
		border: 1px solid rgba(255,255,255,0.06);
		border-radius: 14px;
		background: rgba(255,255,255,0.02);
	}

	.empty-step {
		display: flex;
		align-items: flex-start;
		gap: 14px;
		padding: 10px 0;
	}

	.step-marker {
		width: 28px;
		height: 28px;
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 8px;
		background: rgba(255,255,255,0.04);
		border: 1px solid rgba(255,255,255,0.08);
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		color: #6b7d8e;
		font-weight: 500;
	}

	.empty-step.done .step-marker {
		background: rgba(91,181,166,0.14);
		border-color: rgba(91,181,166,0.25);
		color: #5BB5A6;
	}

	.step-connector {
		width: 1px;
		height: 12px;
		margin-left: 13.5px;
		background: rgba(255,255,255,0.06);
	}

	.step-body {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding-top: 4px;
	}

	.step-title {
		font-size: 13px;
		font-weight: 500;
		color: #c8d6e0;
	}

	.step-desc {
		font-size: 12px;
		color: #6b7d8e;
		line-height: 1.45;
	}

	.step-desc code {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #8fa3b0;
	}

	.freshness-banner {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 14px;
		align-items: start;
		margin: 0 0 18px;
		padding: 14px 16px;
		border: 1px solid rgba(228,164,72,0.28);
		border-radius: 16px;
		background:
			linear-gradient(135deg, rgba(228,164,72,0.16), rgba(228,93,74,0.08)),
			rgba(255,255,255,0.03);
		box-shadow: 0 18px 36px rgba(0,0,0,0.16);
	}

	.freshness-banner.pending {
		border-color: rgba(91,181,166,0.24);
		background:
			linear-gradient(135deg, rgba(91,181,166,0.14), rgba(74,144,217,0.08)),
			rgba(255,255,255,0.03);
	}

	.freshness-label {
		padding: 5px 8px;
		border-radius: 999px;
		background: rgba(255,255,255,0.08);
		color: #f3c47b;
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
	}

	.freshness-banner.pending .freshness-label {
		color: #7fc9bc;
	}

	.freshness-copy {
		display: grid;
		gap: 4px;
	}

	.freshness-copy strong {
		font-size: 14px;
		line-height: 1.35;
		color: #f4f7f9;
	}

	.freshness-copy p {
		margin: 0;
		font-size: 13px;
		line-height: 1.55;
		color: #b7c5cf;
	}

	@media (max-width: 900px) {
		.freshness-banner {
			grid-template-columns: 1fr;
		}
	}

	/* Readiness hero */
	.readiness-hero {
		background: rgba(255,255,255,0.02);
		border: 1px solid rgba(255,255,255,0.05);
		border-radius: 10px;
		padding: 24px 28px;
		margin-bottom: 20px;
	}

	.readiness-top {
		display: flex;
		align-items: center;
		gap: 24px;
		margin-bottom: 20px;
		padding-bottom: 16px;
		border-bottom: 1px solid rgba(255,255,255,0.04);
	}

	.readiness-ring {
		position: relative;
		width: 100px;
		height: 100px;
		flex-shrink: 0;
	}

	.ring-svg {
		width: 100%;
		height: 100%;
		transform: rotate(-90deg);
	}

	.ring-track {
		fill: none;
		stroke: rgba(255,255,255,0.05);
		stroke-width: 6;
	}

	.ring-fill {
		fill: none;
		stroke-width: 6;
		stroke-linecap: round;
		transition: stroke-dasharray 0.6s ease;
	}

	.ring-content {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.ring-score {
		font-family: 'DM Mono', monospace;
		font-size: 32px;
		font-weight: 600;
		line-height: 1;
	}

	.readiness-info {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.readiness-label {
		font-family: 'DM Mono', monospace;
		font-size: 16px;
		font-weight: 600;
		letter-spacing: 2px;
		text-transform: uppercase;
	}

	.readiness-subtitle {
		font-size: 12px;
		color: #7e8f9e;
	}

	.readiness-explain {
		font-size: 12px;
		color: #6b7d8e;
		margin: 4px 0 0;
		line-height: 1.4;
	}

	.readiness-components {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 16px;
	}

	.comp-row {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.comp-header {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.comp-dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.comp-label {
		font-size: 13px;
		color: #a0b0bc;
		letter-spacing: 0.5px;
		font-weight: 500;
	}

	.comp-actual {
		font-family: 'DM Mono', monospace;
		font-size: 13px;
		color: #d0dce4;
		margin-left: 4px;
	}

	.comp-delta {
		font-family: 'DM Mono', monospace;
		font-size: 12px;
	}

	.comp-score {
		font-family: 'DM Mono', monospace;
		font-size: 15px;
		font-weight: 600;
		margin-left: auto;
	}

	.comp-max {
		font-family: 'DM Mono', monospace;
		font-size: 15px;
		color: #5e7282;
	}

	.comp-bar-track {
		height: 4px;
		background: rgba(255,255,255,0.05);
		border-radius: 2px;
		overflow: hidden;
	}

	.comp-bar-fill {
		height: 100%;
		border-radius: 2px;
		transition: width 0.5s ease;
		opacity: 0.8;
	}

	/* ── Unified Metric Cards ── */
	.metric-grid {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 16px;
		margin-bottom: 20px;
	}

	.metric-card {
		background: rgba(255,255,255,0.02);
		border: 1px solid rgba(255,255,255,0.05);
		border-radius: 10px;
		padding: 16px 18px;
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.metric-card-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
	}

	.metric-card-left {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.metric-label {
		font-size: 11px;
		letter-spacing: 1.5px;
		text-transform: uppercase;
		color: #7e8f9e;
	}

	.metric-value-row {
		display: flex;
		align-items: baseline;
		gap: 4px;
	}

	.metric-value {
		font-family: 'DM Mono', monospace;
		font-size: 24px;
		font-weight: 600;
		font-variant-numeric: tabular-nums lining-nums;
		line-height: 1.1;
	}

	.metric-unit {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #6b7d8e;
		letter-spacing: 0.5px;
	}

	.metric-delta {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		margin-top: 2px;
	}

	.metric-card-stats {
		display: flex;
		gap: 14px;
		align-items: flex-start;
		padding-top: 4px;
	}

	.mini-stat {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1px;
	}

	.mini-stat-label {
		font-size: 9px;
		letter-spacing: 1px;
		text-transform: uppercase;
		color: #6b7d8e;
	}

	.mini-stat-value {
		font-family: 'DM Mono', monospace;
		font-size: 13px;
		font-weight: 500;
		color: #a0b0bc;
		font-variant-numeric: tabular-nums lining-nums;
	}

	.metric-chart {
		height: 160px;
		position: relative;
	}

	@media (max-width: 768px) {
		.metric-grid { grid-template-columns: 1fr; }
		.readiness-components { grid-template-columns: 1fr; }
		.readiness-top { flex-direction: column; text-align: center; }
		.metric-card-header { flex-direction: column; gap: 8px; }
		.metric-card-stats { justify-content: flex-start; }
	}
</style>
