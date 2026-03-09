<script lang="ts">
	import { onMount } from 'svelte';
	import { api, type DailyAggregates, type DailyMetric, type DashboardOverview } from '$lib/api';
	import { startRealtimePage } from '$lib/realtime-page';
	import { Chart, chartTooltip, DARK_GRID, DARK_GRID_Y, DARK_BORDER, DARK_TICK } from '$lib/chart-setup';
	import type { ChartConfiguration } from 'chart.js';
	import ScatterChart from '$lib/components/ScatterChart.svelte';
	import TrendRangePicker from '$lib/components/TrendRangePicker.svelte';
	import { type TrendRange, filterByRange, PERIOD_KEY_MAP } from '$lib/trend-range';
	import { fmt } from '$lib/format';
	import { COLORS, withAlpha } from '$lib/colors';

	let data: DailyAggregates | null = $state(null);
	let overview: DashboardOverview | null = $state(null);
	let error: string | null = $state(null);
	let trendRange: TrendRange = $state('3M');
	let canvasRefs: Record<string, HTMLCanvasElement> = $state({});
	let charts: Record<string, Chart<'line'>> = {};

	type MetricConfig = {
		key: string;
		label: string;
		unit: string;
		color: string;
		getValue: (d: DailyMetric) => number | null;
		getSecondary?: (d: DailyMetric) => number | null;
		secondaryLabel?: string;
	};

	const metrics: MetricConfig[] = [
		{ key: 'stress', label: 'Stress', unit: 'avg', color: COLORS.stress, getValue: (d) => d.stress.avg },
		{ key: 'bb', label: 'Body Battery', unit: 'avg', color: COLORS.bodyBattery, getValue: (d) => d.body_battery.avg },
		{ key: 'spo2', label: 'Blood Oxygen', unit: '%', color: COLORS.spo2, getValue: (d) => d.spo2.avg },
		{ key: 'resp', label: 'Respiration', unit: 'br/min', color: COLORS.respiration, getValue: (d) => d.respiration.avg },
		{ key: 'sleep', label: 'Sleep Score', unit: 'pts', color: COLORS.sleep, getValue: (d) => d.sleep.score, getSecondary: (d) => d.sleep.deep_score, secondaryLabel: 'deep' },
		{ key: 'temp', label: 'Skin Temperature', unit: '\u00B0C dev', color: COLORS.skinTemp, getValue: (d) => d.skin_temp.deviation }
	];

	async function fetchData() {
		const [nextData, nextOverview] = await Promise.all([
			api.getDailyAggregates(),
			api.getDashboardOverview()
		]);
		data = nextData;
		overview = nextOverview;
	}

	onMount(() => {
		return startRealtimePage({
			fetchData,
			setError: (message) => {
				error = message;
			},
			setLoading: () => {}
		});
	});

	function latestValid(daily: DailyMetric[], getter: (d: DailyMetric) => number | null): number | null {
		for (let i = daily.length - 1; i >= 0; i--) {
			const v = getter(daily[i]);
			if (v != null) return v;
		}
		return null;
	}

	function createChart(canvas: HTMLCanvasElement, metric: MetricConfig, daily: DailyMetric[]) {
		const labels = daily.map((d) => d.date.slice(5));
		const config: ChartConfiguration<'line'> = {
			type: 'line',
			data: {
				labels,
				datasets: [{
					label: metric.label,
					data: daily.map(metric.getValue),
					borderColor: metric.color,
					backgroundColor: metric.color + '15',
					borderWidth: 2,
					pointRadius: 0,
					pointHoverRadius: 4,
					tension: 0.4,
					spanGaps: true,
					fill: true
				}]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: false },
					tooltip: {
						...chartTooltip(withAlpha(metric.color, '60')),
						titleFont: { family: 'DM Mono', size: 11 },
						bodyFont: { family: 'DM Mono', size: 12 }
					}
				},
				scales: {
					x: {
						grid: DARK_GRID,
						ticks: { ...DARK_TICK, font: { family: 'DM Mono', size: 9 }, maxTicksLimit: 6 },
						border: DARK_BORDER
					},
					y: {
						grid: DARK_GRID_Y,
						ticks: { ...DARK_TICK, font: { family: 'DM Mono', size: 9 }, maxTicksLimit: 5 },
						border: DARK_BORDER,
						beginAtZero: false
					}
				}
			}
		};
		return new Chart(canvas, config);
	}

	let filteredDaily = $derived.by<DailyMetric[]>(() => data ? filterByRange(data.daily, trendRange) : []);

	$effect(() => {
		if (!data) return;
		const daily = filteredDaily;
		for (const metric of metrics) {
			const canvas = canvasRefs[metric.key];
			if (!canvas) continue;
			if (charts[metric.key]) {
				const chart = charts[metric.key];
				chart.data.labels = daily.map((d) => d.date.slice(5));
				chart.data.datasets[0].data = daily.map(metric.getValue);
				chart.update();
			} else {
				charts[metric.key] = createChart(canvas, metric, daily);
			}
		}
	});

	onMount(() => {
		return () => {
			Object.values(charts).forEach((c) => c.destroy());
		};
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

	type CorrelationItem = NonNullable<DashboardOverview['correlations']>[number];

	function makeScatterConfig(corr: CorrelationItem): ChartConfiguration<'scatter'> {
		return {
			type: 'scatter',
			data: {
				datasets: [
					{
						label: corr.label,
						data: corr.points.map((p) => ({ x: p.hrv_nightly, y: p.other_value })),
						backgroundColor: withAlpha(COLORS.hrv, '88'),
						borderColor: withAlpha(COLORS.hrv, 'cc'),
						borderWidth: 1,
						pointRadius: 3,
						pointHoverRadius: 5
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { display: false },
					tooltip: {
						...chartTooltip(withAlpha(COLORS.hrv, '60')),
						callbacks: {
							label: (ctx) => {
								const raw = ctx.raw as { x: number; y: number };
								return `HRV ${raw.x} ms · ${corr.label} ${raw.y}`;
							}
						}
					}
				},
				scales: {
					x: {
						title: {
							display: true,
							text: 'HRV (ms)',
							...DARK_TICK,
							font: { family: 'DM Mono', size: 10 }
						},
						ticks: { ...DARK_TICK, font: { family: 'DM Mono', size: 9 } },
						grid: DARK_GRID,
						border: DARK_BORDER
					},
					y: {
						title: {
							display: true,
							text: corr.label,
							...DARK_TICK,
							font: { family: 'DM Mono', size: 10 }
						},
						ticks: { ...DARK_TICK, font: { family: 'DM Mono', size: 9 } },
						grid: DARK_GRID_Y,
						border: DARK_BORDER
					}
				}
			}
		};
	}
</script>

<svelte:head>
	<title>Dashboard - Garmin Stats</title>
</svelte:head>

{#if error}
	<div class="topo-error">
		<p>Error: {error}</p>
	</div>
{:else if !data}
	<div class="topo-loading">
		<div class="loading-pulse"></div>
		<span>Mapping terrain data...</span>
	</div>
{:else}
	<!-- Summary strip -->
	<div class="summary-strip">
		<div class="strip-border"></div>
		<div class="strip-content">
			{#each metrics as metric}
				{@const val = latestValid(filteredDaily, metric.getValue)}
				<div class="strip-item">
					<span class="strip-label">{metric.label}</span>
					<span class="strip-value" style="color:{metric.color}">{fmt(val)}</span>
					<span class="strip-unit">{metric.unit}</span>
				</div>
			{/each}
		</div>
		<div class="strip-border"></div>
	</div>

	<div class="strip-date-row">
		<div class="strip-date">
			{data.days.length} days collected &mdash; {data.days[0]} to {data.days[data.days.length - 1]}
		</div>
		<TrendRangePicker bind:value={trendRange} />
	</div>

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
					<div class="comp-row">
						<div class="comp-header">
							<div class="comp-dot" style="background:{info.color}"></div>
							<span class="comp-label">{info.label}</span>
							<span class="comp-score" style="color:{info.color}">{Math.round(val)}</span>
							<span class="comp-max">/ 25</span>
						</div>
						<div class="comp-bar-track">
							<div class="comp-bar-fill" style="width:{(val / 25) * 100}%; background:{info.color}"></div>
						</div>
						<p class="comp-desc">{info.description}</p>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Cross-domain correlations -->
	{#if overview && overview.correlations.length > 0}
		<div class="correlation-section">
			<h2 class="section-heading">Cross-Domain Correlations</h2>
			<div class="correlation-grid">
				{#each overview.correlations as corr}
					<div class="correlation-card">
						<div class="corr-header">
							<span class="corr-title">HRV vs {corr.label}</span>
							{#if corr.r_value != null}
								<span class="corr-r" style="color:{COLORS.hrv}">r = {corr.r_value}</span>
							{/if}
						</div>
						<ScatterChart config={makeScatterConfig(corr)} height={200} />
						<p class="corr-subtitle">{corr.sample_count} nights</p>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Metric grid -->
	<div class="metric-grid">
		{#each metrics as metric}
			{@const val = latestValid(data.daily, metric.getValue)}
			{@const secVal = metric.getSecondary ? latestValid(data.daily, metric.getSecondary) : null}
			<div class="metric-card" style="--accent:{metric.color}">
				<div class="card-header">
					<div class="card-title-row">
						<div class="card-dot" style="background:{metric.color}"></div>
						<h3 class="card-title">{metric.label}</h3>
					</div>
					<div class="card-values">
						<span class="card-primary" style="color:{metric.color}">{fmt(val)}</span>
						<span class="card-unit">{metric.unit}</span>
						{#if secVal != null}
							<span class="card-secondary">{metric.secondaryLabel} {fmt(secVal)}</span>
						{/if}
					</div>
				</div>
				<div class="card-chart">
					<canvas bind:this={canvasRefs[metric.key]}></canvas>
				</div>
			</div>
		{/each}
	</div>
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

	.summary-strip {
		margin: 0 0 0;
	}

	.strip-border {
		height: 1px;
		background: linear-gradient(90deg, transparent, rgba(91,181,166,0.35), transparent);
	}

	.strip-content {
		display: flex;
		justify-content: space-between;
		padding: 18px 0;
	}

	.strip-item {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 4px;
	}

	.strip-label {
		font-size: 9px;
		letter-spacing: 1.5px;
		text-transform: uppercase;
		color: #5e7282;
	}

	.strip-value {
		font-family: 'DM Mono', monospace;
		font-size: 24px;
		font-weight: 500;
		line-height: 1;
	}

	.strip-unit {
		font-family: 'DM Mono', monospace;
		font-size: 9px;
		color: #4a5c6a;
		letter-spacing: 1px;
	}

	.strip-date-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin: 12px 0 20px;
	}

	.strip-date {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		color: #4a5c6a;
		letter-spacing: 2px;
		text-transform: uppercase;
	}

	/* Readiness hero */
	.readiness-hero {
		background: rgba(255,255,255,0.02);
		border: 1px solid rgba(255,255,255,0.05);
		border-radius: 10px;
		padding: 28px;
		margin-bottom: 20px;
	}

	.readiness-top {
		display: flex;
		align-items: center;
		gap: 24px;
		margin-bottom: 24px;
		padding-bottom: 20px;
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
		font-size: 11px;
		color: #5e7282;
	}

	.readiness-explain {
		font-size: 11px;
		color: #4a5c6a;
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
		font-size: 11px;
		color: #8a9baa;
		letter-spacing: 0.5px;
		font-weight: 500;
	}

	.comp-score {
		font-family: 'DM Mono', monospace;
		font-size: 13px;
		font-weight: 600;
		margin-left: auto;
	}

	.comp-max {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		color: #3a4a56;
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

	.comp-desc {
		font-size: 10px;
		color: #4a5c6a;
		margin: 0;
		line-height: 1.3;
	}

	/* Correlations */
	.correlation-section {
		margin-bottom: 20px;
	}

	.section-heading {
		font-size: 11px;
		font-weight: 600;
		letter-spacing: 1.5px;
		text-transform: uppercase;
		color: #8a9baa;
		margin: 0 0 12px;
	}

	.correlation-grid {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 12px;
	}

	.correlation-card {
		background: rgba(255,255,255,0.02);
		border: 1px solid rgba(255,255,255,0.05);
		border-radius: 10px;
		padding: 16px;
	}

	.corr-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 10px;
	}

	.corr-title {
		font-size: 11px;
		font-weight: 600;
		letter-spacing: 1px;
		text-transform: uppercase;
		color: #8a9baa;
	}

	.corr-r {
		font-family: 'DM Mono', monospace;
		font-size: 13px;
		font-weight: 500;
	}

	.corr-subtitle {
		font-family: 'DM Mono', monospace;
		font-size: 10px;
		color: #4a5c6a;
		margin: 8px 0 0;
	}

	/* Metric grid */
	.metric-grid {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 12px;
	}

	.metric-card {
		background: rgba(255,255,255,0.02);
		border: 1px solid rgba(255,255,255,0.05);
		border-radius: 10px;
		padding: 16px;
		transition: all 0.3s;
		position: relative;
		overflow: hidden;
	}

	.metric-card::before {
		content: '';
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		height: 2px;
		background: var(--accent);
		opacity: 0.4;
	}

	.metric-card:hover {
		background: rgba(255,255,255,0.04);
		border-color: rgba(255,255,255,0.08);
		transform: translateY(-2px);
	}

	.card-header {
		margin-bottom: 12px;
	}

	.card-title-row {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-bottom: 6px;
	}

	.card-dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
	}

	.card-title {
		font-size: 11px;
		font-weight: 600;
		letter-spacing: 1.5px;
		text-transform: uppercase;
		color: #8a9baa;
		margin: 0;
	}

	.card-values {
		display: flex;
		align-items: baseline;
		gap: 6px;
	}

	.card-primary {
		font-family: 'DM Mono', monospace;
		font-size: 24px;
		font-weight: 500;
		line-height: 1;
	}

	.card-unit {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #4a5c6a;
	}

	.card-secondary {
		font-family: 'DM Mono', monospace;
		font-size: 11px;
		color: #5e7282;
		margin-left: auto;
	}

	.card-chart {
		height: 140px;
		position: relative;
	}

	@media (max-width: 1200px) {
		.metric-grid { grid-template-columns: repeat(2, 1fr); }
		.correlation-grid { grid-template-columns: repeat(2, 1fr); }
	}

	@media (max-width: 640px) {
		.metric-grid { grid-template-columns: 1fr; }
		.correlation-grid { grid-template-columns: 1fr; }
		.strip-content { flex-wrap: wrap; gap: 12px; justify-content: center; }
		.readiness-components { grid-template-columns: 1fr; }
		.readiness-top { flex-direction: column; text-align: center; }
	}
</style>
