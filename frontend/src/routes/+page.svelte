<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type DailyAggregates, type DashboardOverview, type IngestStatus } from '$lib/api';
	import { startRealtimePage } from '$lib/realtime-page';
	import { Chart, DARK_BORDER, DARK_GRID_Y, DARK_TICK, chartTooltip } from '$lib/chart-setup';
	import type { ChartConfiguration } from 'chart.js';
	import { fmt, fmtSigned } from '$lib/format';
	import { COLORS } from '$lib/colors';

	let data: DailyAggregates | null = $state(null);
	let overview: DashboardOverview | null = $state(null);
	let ingestStatus: IngestStatus | null = $state(null);
	let emptyState: IngestStatus | null = $state(null);
	let error: string | null = $state(null);
	let sparkCanvases: Record<string, HTMLCanvasElement> = $state({});
	let sparkCharts: Record<string, Chart<'line'>> = {};

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

	function emptyStateTitle(status: IngestStatus): string {
		return status.days_on_disk === 0
			? 'No Garmin data is loaded yet.'
			: 'Garmin files are present, but nothing is ingested yet.';
	}

	function emptyStateDetail(status: IngestStatus): string {
		return status.days_on_disk === 0
			? 'Create the data directory, drop in Garmin export archives named like YYYY-MM-DD.zip, and the watcher will ingest them as they arrive.'
			: 'The backend is up and the watcher is waiting. Trigger one ingest to build the first dashboard snapshot, then the app will populate automatically.';
	}

	function emptyStateCommand(status: IngestStatus): string {
		return status.days_on_disk === 0
			? 'mkdir -p data\n# copy Garmin export archives like data/2026-03-15.zip\ncurl -X POST http://127.0.0.1:8000/api/ingest'
			: 'curl -X POST http://127.0.0.1:8000/api/ingest';
	}

	onMount(() => {
		return startRealtimePage({
			fetchData,
			setError: (message) => { error = message; },
			setLoading: () => {}
		});
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
		<div class="empty-hero">
			<p class="empty-eyebrow">Empty Runtime</p>
			<h1>{emptyStateTitle(emptyState)}</h1>
			<p class="empty-copy">{emptyStateDetail(emptyState)}</p>
		</div>

		<div class="empty-grid">
			<div class="empty-card">
				<span>Days in DB</span>
				<strong>{emptyState.days_in_db}</strong>
				<small>No daily metrics have been materialized yet.</small>
			</div>
			<div class="empty-card">
				<span>Days on disk</span>
				<strong>{emptyState.days_on_disk}</strong>
				<small>Detected Garmin export days available to ingest.</small>
			</div>
			<div class="empty-card accent">
				<span>Watcher status</span>
				<strong>{emptyState.days_on_disk === 0 ? 'Idle' : 'Ready'}</strong>
				<small>{emptyState.needs_ingest ? 'New files will be ingested on update.' : 'Waiting for the first import.'}</small>
			</div>
		</div>

		<div class="empty-actions">
			<div class="empty-panel">
				<p class="empty-panel-title">Quick start</p>
				<pre>{emptyStateCommand(emptyState)}</pre>
			</div>
			<div class="empty-panel">
				<p class="empty-panel-title">Expected layout</p>
				<p><code>data/YYYY-MM-DD.zip</code> archives are the input. The backend recreates <code>data/</code> automatically if it is missing.</p>
				<p>Once the first ingest completes, this dashboard will swap from the empty state to live recovery cards without a restart.</p>
			</div>
		</div>
	</section>
{:else if !data}
	<div class="topo-loading">
		<div class="loading-pulse"></div>
		<span>Mapping terrain data...</span>
	</div>
{:else}
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
		display: grid;
		gap: 20px;
		padding: 20px 0 12px;
	}

	.empty-hero,
	.empty-card,
	.empty-panel {
		border: 1px solid rgba(255,255,255,0.06);
		background: rgba(255,255,255,0.03);
		border-radius: 18px;
		box-shadow: 0 18px 40px rgba(0,0,0,0.18);
	}

	.empty-hero {
		padding: 28px;
		background:
			radial-gradient(circle at top left, rgba(91,181,166,0.12), transparent 32%),
			radial-gradient(circle at right, rgba(155,107,205,0.12), transparent 28%),
			linear-gradient(145deg, rgba(13,21,32,0.96), rgba(17,28,42,0.92));
	}

	.empty-eyebrow,
	.empty-card span,
	.empty-panel-title {
		margin: 0;
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: #8fa3b0;
	}

	.empty-hero h1 {
		margin: 10px 0 0;
		max-width: 12ch;
		font-family: 'Iowan Old Style', 'Palatino Linotype', serif;
		font-size: clamp(38px, 6vw, 64px);
		line-height: 0.94;
		color: #eef5f8;
	}

	.empty-copy,
	.empty-card small,
	.empty-panel p {
		color: #aec0cb;
		line-height: 1.6;
	}

	.empty-copy {
		max-width: 64ch;
		margin: 16px 0 0;
		font-size: 15px;
	}

	.empty-grid,
	.empty-actions {
		display: grid;
		gap: 14px;
	}

	.empty-grid {
		grid-template-columns: repeat(3, minmax(0, 1fr));
	}

	.empty-card,
	.empty-panel {
		padding: 18px;
	}

	.empty-card strong {
		display: block;
		margin-top: 10px;
		font-size: 36px;
		color: #eef5f8;
	}

	.empty-card.accent {
		background: linear-gradient(145deg, rgba(91,181,166,0.12), rgba(155,107,205,0.12));
	}

	.empty-actions {
		grid-template-columns: minmax(320px, 0.9fr) minmax(0, 1.1fr);
	}

	.empty-panel pre {
		margin: 14px 0 0;
		padding: 14px;
		border-radius: 14px;
		background: rgba(6, 11, 18, 0.72);
		border: 1px solid rgba(255,255,255,0.06);
		overflow-x: auto;
		white-space: pre-wrap;
		color: #dce9f0;
		font-family: 'DM Mono', monospace;
		font-size: 12px;
		line-height: 1.6;
	}

	.empty-panel code {
		font-family: 'DM Mono', monospace;
		color: #dce9f0;
	}

	@media (max-width: 900px) {
		.empty-grid,
		.empty-actions {
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
